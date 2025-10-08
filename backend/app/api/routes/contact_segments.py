"""API endpoints for managing contact segments and routing policies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_pagination_params,
    require_contacts_read,
    require_contacts_write,
)
from app.core.database import get_db
from app.services.contacts import ContactSegmentService

router = APIRouter()


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
    items = [ContactSegmentResponse.model_validate(segment) for segment in segments]

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
    return ContactSegmentResponse.model_validate(segment)


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

    return ContactSegmentResponse.model_validate(segment)


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

    return ContactSegmentResponse.model_validate(segment)


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
        created_memberships=[
            SegmentMembershipResponse.model_validate(membership) for membership in created_memberships
        ],
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

    return SegmentPolicyResponse.model_validate(policy)
