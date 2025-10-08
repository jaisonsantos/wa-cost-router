"""API endpoints for managing contact catalog entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_pagination_params,
    require_contacts_read,
    require_contacts_write,
)
from app.core.database import get_db
from app.models.models import ContactStatusEnum, OptInStatusEnum
from app.services.contacts import ContactRepository

router = APIRouter()


class ContactBase(BaseModel):
    """Shared fields for contact payloads."""

    model_config = ConfigDict(extra="forbid")

    external_id: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: ContactStatusEnum | None = None
    attributes: dict[str, Any] | None = None
    source: str | None = None
    source_metadata: dict[str, Any] | None = None
    proof_hash: str | None = None


class ContactCreate(ContactBase):
    """Payload accepted when creating new contacts."""

    status: ContactStatusEnum = ContactStatusEnum.active
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class ContactUpdate(ContactBase):
    """Payload accepted when partially updating contacts."""

    pass


class ContactResponse(BaseModel):
    """Public representation of a contact resource."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    external_id: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: ContactStatusEnum
    attributes: dict[str, Any] | None = None
    source: str
    source_metadata: dict[str, Any] | None = None
    proof_hash: str | None = None
    created_at: datetime
    updated_at: datetime


class ContactListResponse(BaseModel):
    """Envelope returned by collection endpoints."""

    model_config = ConfigDict(extra="forbid")

    items: List[ContactResponse]
    limit: int
    offset: int
    count: int


@router.get("/", response_model=ContactListResponse)
def list_contacts(
    pagination: PaginationParams = Depends(get_pagination_params),
    status: ContactStatusEnum | None = Query(None, description="Contact lifecycle status."),
    channel: str | None = Query(None, description="Filter opt-ins by channel type."),
    opt_in_status: List[OptInStatusEnum] | None = Query(
        None, alias="opt_in_status", description="Filter by opt-in status for the selected channel."
    ),
    segment_ids: List[UUID] | None = Query(
        None, alias="segment_id", description="Filter contacts that belong to specific segment IDs."
    ),
    segment_slugs: List[str] | None = Query(
        None, alias="segment_slug", description="Filter contacts that belong to specific segment slugs."
    ),
    channel_address: str | None = Query(
        None,
        alias="channel_address",
        description="Restrict opt-ins to a specific channel address (phone/email).",
    ),
    current_user: dict = Depends(require_contacts_read),
    db: Session = Depends(get_db),
):
    """Return a paginated subset of contacts for the authenticated organization."""

    repository = ContactRepository(db)
    contacts = repository.list_contacts(
        org_id=current_user["org_id"],
        status=status,
        segment_ids=segment_ids,
        segment_slugs=segment_slugs,
        channel=channel,
        channel_status=opt_in_status,
        channel_address=channel_address,
        limit=pagination.limit,
        offset=pagination.offset,
    )

    items = [ContactResponse.model_validate(contact) for contact in contacts]

    return ContactListResponse(
        items=items,
        limit=pagination.limit,
        offset=pagination.offset,
        count=len(items),
    )


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Create a new contact scoped to the authenticated organization."""

    repository = ContactRepository(db)
    contact = repository.create_contact(
        org_id=current_user["org_id"],
        **payload.model_dump(exclude_unset=True),
    )
    return ContactResponse.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Update a contact belonging to the authenticated organization."""

    repository = ContactRepository(db)
    updates = payload.model_dump(exclude_unset=True)
    contact = repository.update_contact(
        org_id=current_user["org_id"],
        contact_id=contact_id,
        **updates,
    )

    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    return ContactResponse.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: UUID,
    current_user: dict = Depends(require_contacts_write),
    db: Session = Depends(get_db),
):
    """Remove a contact from the authenticated organization."""

    repository = ContactRepository(db)
    deleted = repository.delete_contact(org_id=current_user["org_id"], contact_id=contact_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    return None
