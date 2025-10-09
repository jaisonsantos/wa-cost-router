"""API endpoints for managing contact segments and routing policies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_pagination_params,
    require_contacts_read,
    require_contacts_write,
)
from app.core.database import get_db
from app.models.models import ContactSegment, ContactSegmentMembership, ContactSegmentPolicy
from app.services.contacts import ContactSegmentService

router = APIRouter()


def _as_optional_dict(value: Any) -> dict[str, Any] | None:
    """Return dictionaries as-is and discard unexpected JSON payloads."""

    if isinstance(value, dict):
        return value
    return None


def _normalize_segment_source(value: Any) -> str:
    """Guarantee a stable source label when legacy rows omit it."""

    if isinstance(value, str) and value.strip():
        return value
    return "manual"


def _coerce_datetime(value: Any) -> datetime:
    """Return a timezone-aware datetime, defaulting to the current UTC instant."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    return datetime.now(timezone.utc)


def _normalize_slug(value: Any, *, default: str) -> str:
    """Return a slug-like string even if legacy records omit it."""

    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate

    return default


def _normalize_name(value: Any, *, fallback: str) -> str:
    """Provide a human-friendly segment name when the stored value is missing."""

    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate

    return fallback


def _coerce_optional_string(value: Any) -> str | None:
    """Return a stripped string when possible, otherwise ``None``."""

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _serialize_policy(policy: ContactSegmentPolicy | None) -> SegmentPolicyResponse | None:
    """Convert stored routing policies into the public response schema."""

    if policy is None:
        return None

    raw_payload = {
        "limits": _as_optional_dict(getattr(policy, "limits", None)) or {},
        "opt_out": _as_optional_dict(getattr(policy, "opt_out", None)) or {},
    }

    try:
        return SegmentPolicyResponse.model_validate(raw_payload)
    except ValidationError:
        # Default to an empty policy when the stored JSON contains unexpected
        # shapes so the endpoint can continue serving responses.
        return SegmentPolicyResponse.model_construct(
            limits=SegmentLimits(),
            opt_out=SegmentOptOutPolicy(),
        )


def _serialize_segment(segment: ContactSegment) -> ContactSegmentResponse:
    """Normalize a segment ORM model into an API response."""

    policy_model = _serialize_policy(getattr(segment, "policy", None))
    segment_id = getattr(segment, "id", None)
    fallback_slug = f"segment-{segment_id}" if segment_id is not None else "segment-legacy"
    normalized_slug = _normalize_slug(getattr(segment, "slug", None), default=fallback_slug)
    normalized_name = _normalize_name(getattr(segment, "name", None), fallback=normalized_slug)
    raw_payload = {
        "id": segment.id,
        "org_id": segment.org_id,
        "slug": normalized_slug,
        "name": normalized_name,
        "description": _coerce_optional_string(getattr(segment, "description", None)),
        "criteria": _as_optional_dict(getattr(segment, "criteria", None)),
        "source": _normalize_segment_source(getattr(segment, "source", None)),
        "source_metadata": _as_optional_dict(getattr(segment, "source_metadata", None)),
        "proof_hash": _coerce_optional_string(getattr(segment, "proof_hash", None)),
        "created_at": _coerce_datetime(getattr(segment, "created_at", None)),
        "updated_at": _coerce_datetime(getattr(segment, "updated_at", None)),
        "policy": policy_model.model_dump() if policy_model else None,
    }

    try:
        return ContactSegmentResponse.model_validate(raw_payload)
    except ValidationError:
        return ContactSegmentResponse.model_construct(**raw_payload)


def _normalize_membership_origin(value: Any) -> str:
    """Ensure membership records expose a traceable origin label."""

    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate

    return "legacy"


def _serialize_membership(
    membership: ContactSegmentMembership,
) -> SegmentMembershipResponse:
    """Serialize membership rows ensuring optional metadata stays well-formed."""

    raw_payload = {
        "id": membership.id,
        "org_id": membership.org_id,
        "contact_id": membership.contact_id,
        "segment_id": membership.segment_id,
        "membership_origin": _normalize_membership_origin(
            getattr(membership, "membership_origin", None)
        ),
        "valid_from": _coerce_datetime(getattr(membership, "valid_from", None)),
        "valid_to": (
            _coerce_datetime(membership.valid_to)
            if getattr(membership, "valid_to", None) is not None
            else None
        ),
        "source": _normalize_segment_source(getattr(membership, "source", None)),
        "source_metadata": _as_optional_dict(getattr(membership, "source_metadata", None)),
    }

    try:
        return SegmentMembershipResponse.model_validate(raw_payload)
    except ValidationError:
        return SegmentMembershipResponse.model_construct(**raw_payload)


class SegmentLimits(BaseModel):
    """Rate limit configuration for a contact segment."""

    model_config = ConfigDict(extra="forbid")

    max_daily_messages: int | None = Field(default=None, ge=0)
    max_weekly_messages: int | None = Field(default=None, ge=0)
    max_monthly_messages: int | None = Field(default=None, ge=0)


class SegmentOptOutPolicy(BaseModel):
    """Opt-out handling strategy for a contact segment."""

    model_config = ConfigDict(extra="forbid")

    enforce: bool = True
    global_opt_out: bool = False
    channels: List[str] = Field(default_factory=list)
    grace_period_hours: int | None = Field(default=None, ge=0)


class SegmentPolicyPayload(BaseModel):
    """Payload accepted to configure routing policies for a segment."""

    model_config = ConfigDict(extra="forbid")

    limits: SegmentLimits = Field(default_factory=SegmentLimits)
    opt_out: SegmentOptOutPolicy = Field(default_factory=SegmentOptOutPolicy)


class SegmentPolicyResponse(SegmentPolicyPayload):
    """Public representation of stored routing policies."""

    model_config = ConfigDict(from_attributes=True)


class ContactSegmentBase(BaseModel):
    """Shared fields for contact segment payloads."""

    model_config = ConfigDict(extra="forbid")

    slug: str | None = None
    name: str | None = None
    description: str | None = None
    criteria: dict[str, Any] | None = None
    source: str | None = None
    source_metadata: dict[str, Any] | None = None
    proof_hash: str | None = None


class ContactSegmentCreate(ContactSegmentBase):
    """Payload used to create new contact segments."""

    slug: str
    name: str
    source: str = "manual"
    criteria: dict[str, Any] = Field(default_factory=dict)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class ContactSegmentUpdate(ContactSegmentBase):
    """Payload accepted when updating contact segments."""

    pass


class ContactSegmentResponse(BaseModel):
    """Public representation of a contact segment resource."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    slug: str
    name: str
    description: str | None = None
    criteria: dict[str, Any] | None = None
    source: str
    source_metadata: dict[str, Any] | None = None
    proof_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    policy: SegmentPolicyResponse | None = None


class ContactSegmentListResponse(BaseModel):
    """Envelope returned by collection endpoints."""

    model_config = ConfigDict(extra="forbid")

    items: List[ContactSegmentResponse]
    limit: int
    offset: int
    count: int


class SegmentMembershipResponse(BaseModel):
    """Representation of a segment membership association."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    contact_id: UUID
    segment_id: UUID
    membership_origin: str
    valid_from: datetime
    valid_to: datetime | None = None
    source: str
    source_metadata: dict[str, Any] | None = None


class SegmentContactsRequest(BaseModel):
    """Input payload for bulk membership operations."""

    model_config = ConfigDict(extra="forbid")

    contact_ids: List[UUID] = Field(..., min_length=1)
    membership_origin: str = Field(default="manual", min_length=1)
    source: str = Field(default="manual", min_length=1)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentContactsResponse(BaseModel):
    """Output payload summarizing membership operations."""

    model_config = ConfigDict(extra="forbid")

    segment_id: UUID
    created_memberships: List[SegmentMembershipResponse]
    missing_contact_ids: List[UUID]
    already_associated: List[UUID]


@router.get("/", response_model=ContactSegmentListResponse)
def list_contact_segments(
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: dict = Depends(require_contacts_read),
    db: Session = Depends(get_db),
):
    """Return a paginated subset of contact segments."""

    service = ContactSegmentService(db)
    segments = service.list_segments(
        org_id=current_user["org_id"],
        limit=pagination.limit,
        offset=pagination.offset,
    )
    items = [_serialize_segment(segment) for segment in segments]

    return ContactSegmentListResponse(
        items=items,
        limit=pagination.limit,
        offset=pagination.offset,
        count=len(items),
    )


@router.post("/", response_model=ContactSegmentResponse, status_code=status.HTTP_201_CREATED)
def create_contact_segment(
    payload: ContactSegmentCreate,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Create a new contact segment scoped to the authenticated organization."""

    service = ContactSegmentService(db)
    segment = service.create_segment(
        org_id=current_user["org_id"],
        **payload.model_dump(exclude_unset=True),
    )
    return _serialize_segment(segment)


@router.get("/{segment_id}", response_model=ContactSegmentResponse)
def get_contact_segment(
    segment_id: UUID,
    current_user: dict = Depends(require_contacts_read),
    db: Session = Depends(get_db),
):
    """Retrieve a contact segment by identifier."""

    service = ContactSegmentService(db)
    segment = service.get_segment(org_id=current_user["org_id"], segment_id=segment_id)

    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    return _serialize_segment(segment)


@router.patch("/{segment_id}", response_model=ContactSegmentResponse)
def update_contact_segment(
    segment_id: UUID,
    payload: ContactSegmentUpdate,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Update an existing contact segment."""

    service = ContactSegmentService(db)
    updates = payload.model_dump(exclude_unset=True)
    segment = service.update_segment(
        org_id=current_user["org_id"],
        segment_id=segment_id,
        **updates,
    )

    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    return _serialize_segment(segment)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_segment(
    segment_id: UUID,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Delete a contact segment and all memberships."""

    service = ContactSegmentService(db)
    deleted = service.delete_segment(org_id=current_user["org_id"], segment_id=segment_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    return None


@router.post("/{segment_id}/contacts", response_model=SegmentContactsResponse)
def add_contacts_to_segment(
    segment_id: UUID,
    payload: SegmentContactsRequest,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Associate contacts with the selected segment."""

    service = ContactSegmentService(db)
    segment = service.get_segment(org_id=current_user["org_id"], segment_id=segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    created_memberships, missing_contacts, already_associated = service.add_contacts_to_segment(
        org_id=current_user["org_id"],
        segment_id=segment_id,
        contact_ids=payload.contact_ids,
        membership_origin=payload.membership_origin,
        source=payload.source,
        source_metadata=payload.source_metadata,
    )

    return SegmentContactsResponse(
        segment_id=segment_id,
        created_memberships=[_serialize_membership(membership) for membership in created_memberships],
        missing_contact_ids=missing_contacts,
        already_associated=already_associated,
    )


@router.delete("/{segment_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_contact_from_segment(
    segment_id: UUID,
    contact_id: UUID,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Remove an active membership from a contact segment."""

    service = ContactSegmentService(db)
    segment = service.get_segment(org_id=current_user["org_id"], segment_id=segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    removed = service.remove_contact_from_segment(
        org_id=current_user["org_id"],
        segment_id=segment_id,
        contact_id=contact_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact is not associated with this segment",
        )

    return None


@router.put("/{segment_id}/policy", response_model=SegmentPolicyResponse)
def upsert_segment_policy(
    segment_id: UUID,
    payload: SegmentPolicyPayload,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Configure routing limits and opt-out rules for the segment."""

    service = ContactSegmentService(db)
    segment = service.get_segment(org_id=current_user["org_id"], segment_id=segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    policy = service.upsert_policy(
        org_id=current_user["org_id"],
        segment_id=segment_id,
        limits=payload.limits.model_dump(exclude_none=True),
        opt_out=payload.opt_out.model_dump(exclude_none=True),
    )

    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    serialized = _serialize_policy(policy)
    if serialized is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    return serialized
