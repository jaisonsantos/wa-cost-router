"""Pydantic models and validators for routing rule actions."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.models.models import Provider


class RoutingRuleActions(BaseModel):
    """Structured representation of the routing rule actions payload."""

    channel: Optional[str] = Field(default=None, description="Channel enforced by the rule")
    primary_provider: Optional[UUID] = Field(default=None, description="Primary provider UUID")
    fallback_chain: List[UUID] = Field(default_factory=list, description="Fallback providers UUIDs")

    @field_validator("channel")
    @classmethod
    def _normalize_channel(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("channel must not be blank when provided")
        return normalized

    @field_validator("fallback_chain", mode="before")
    @classmethod
    def _ensure_iterable(cls, value: Optional[Iterable[UUID]]) -> List[UUID]:
        if value in (None, ""):
            return []
        if isinstance(value, (str, bytes)):
            raise ValueError("fallback_chain must be an iterable of provider ids")
        if isinstance(value, Iterable):
            return list(value)
        raise ValueError("fallback_chain must be an iterable of provider ids")

    def all_providers(self) -> Sequence[UUID]:
        identifiers: List[UUID] = []
        if self.primary_provider is not None:
            identifiers.append(self.primary_provider)
        identifiers.extend(self.fallback_chain)
        return identifiers


class RoutingRuleValidationError(ValueError):
    """Raised when routing rule actions fail validation."""


def ensure_providers_match_channel(
    db: Session, org_id: UUID, actions: RoutingRuleActions
) -> None:
    """Ensure all listed providers exist for the org and match the rule channel."""

    provider_ids = actions.all_providers()
    if not provider_ids:
        return

    records = (
        db.query(Provider.id, Provider.type)
        .filter(Provider.org_id == org_id)
        .filter(Provider.id.in_(provider_ids))
        .all()
    )

    found_ids = {record.id for record in records}
    missing = set(provider_ids) - found_ids
    if missing:
        raise RoutingRuleValidationError(
            f"Unknown provider ids for org {org_id}: {', '.join(str(item) for item in missing)}"
        )

    if actions.channel is None:
        return

    normalized_channel = actions.channel
    mismatched = [
        str(record.id)
        for record in records
        if (record.type or "").strip().lower() != normalized_channel
    ]
    if mismatched:
        raise RoutingRuleValidationError(
            "Providers do not match rule channel: " + ", ".join(mismatched)
        )


__all__ = [
    "RoutingRuleActions",
    "RoutingRuleValidationError",
    "ensure_providers_match_channel",
]
