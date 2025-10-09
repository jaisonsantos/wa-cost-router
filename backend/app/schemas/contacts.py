"""Pydantic schemas for the contacts bounded context."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.normalization import normalize_international_phone, strip_to_none
from app.models.models import (
    ContactImportStatusEnum,
    ContactStatusEnum,
    OptInStatusEnum,
)


class ContactBase(BaseModel):
    """Shared attributes for contact creation and update payloads."""

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

    @field_validator(
        "external_id",
        "full_name",
        "first_name",
        "last_name",
        "source",
        "proof_hash",
        mode="before",
    )
    @classmethod
    def _trim_optional_strings(cls, value: Any) -> Any:
        return strip_to_none(value)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: Any) -> Any:
        return strip_to_none(value)

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: Any) -> Any:
        return normalize_international_phone(value)


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


class ContactImportJobResponse(BaseModel):
    """Representation of an asynchronous contact import job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    requested_by: str
    input_uri: str | None
    status: ContactImportStatusEnum
    total_rows: int
    processed_rows: int
    error_rows: int
    error_report_uri: str | None
    source: str
    source_metadata: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactConsentAuditItem(BaseModel):
    """Representation of a single consent audit event."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    opt_in_id: UUID | None = None
    opt_in_version: int | None = None
    channel: str
    channel_address: str
    status: OptInStatusEnum
    source: str
    agent: str
    request_ip: str | None = None
    recorded_at: datetime
    evidence_uri: str | None = None
    proof_hash: str | None = None
    context: dict[str, Any] | None = None


class ContactConsentHistoryResponse(BaseModel):
    """Envelope for consent audit history listings."""

    model_config = ConfigDict(extra="forbid")

    items: List[ContactConsentAuditItem]
    count: int


__all__ = [
    "ContactBase",
    "ContactCreate",
    "ContactUpdate",
    "ContactResponse",
    "ContactListResponse",
    "ContactImportJobResponse",
    "ContactConsentAuditItem",
    "ContactConsentHistoryResponse",
]
