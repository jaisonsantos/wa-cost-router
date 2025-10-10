"""Helpers to resolve contact routing preferences and enforce opt-ins."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Contact, ContactChannelOptIn, OptInStatusEnum
from app.services.contacts.repository import ContactRepository

PHONE_CHANNELS = {"sms", "whatsapp"}


class ContactOptOutError(Exception):
    """Raised when a routing decision would violate contact consent."""

    def __init__(
        self,
        message: str = "Contact has no active opt-in for the requested channel.",
        *,
        contact_id: Optional[UUID] = None,
        channel: Optional[str] = None,
        channel_address: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.contact_id = contact_id
        self.channel = channel
        self.channel_address = channel_address


def _normalize_channel(channel: Optional[str]) -> Optional[str]:
    if channel is None:
        return None
    return str(channel).strip().lower()


def _normalize_address(address: Optional[str], *, channel: Optional[str] = None) -> Optional[str]:
    if address is None:
        return None

    normalized_channel = _normalize_channel(channel)
    if normalized_channel in PHONE_CHANNELS:
        return ContactRepository._normalize_phone(address)

    value = str(address).strip()
    if not value:
        return None

    if normalized_channel == "email":
        return value.lower()

    return value.lower()


@dataclass
class ContactRoutingPreferences:
    """Represents the routing preferences inferred from contact opt-ins."""

    contact_id: Optional[UUID]
    normalized_address: Optional[str]
    allowed_channels: Dict[str, Set[str]] = field(default_factory=dict)

    @property
    def contact_exists(self) -> bool:
        return self.contact_id is not None

    def has_allowed_channels_for(self, address: Optional[str]) -> bool:
        """Return True if there is at least one granted opt-in for the address."""

        if not self.allowed_channels:
            return False

        if address is None and self.normalized_address is None:
            return any(bool(addresses) for addresses in self.allowed_channels.values())

        for channel_key, addresses in self.allowed_channels.items():
            normalized = _normalize_address(address or self.normalized_address, channel=channel_key)
            if normalized is not None and normalized in addresses:
                return True
        return False

    def is_channel_allowed(self, channel: Optional[str], address: Optional[str]) -> bool:
        """Return True if the channel/address combination is permitted."""

        normalized_channel = _normalize_channel(channel)
        if not normalized_channel:
            return False

        addresses = self.allowed_channels.get(normalized_channel)
        if not addresses:
            return False

        if address is None:
            return True

        normalized_address = _normalize_address(address, channel=normalized_channel)
        return normalized_address in addresses if normalized_address is not None else False

    def known_channels(self) -> Set[str]:
        return set(self.allowed_channels.keys())


class ContactPreferenceResolver:
    """Load the latest consent state for a contact."""

    def __init__(self, db: Session, org_id: str) -> None:
        self.db = db
        self.org_id = org_id
        self.repository = ContactRepository(db)

    def load(
        self,
        *,
        channel: Optional[str],
        channel_address: Optional[str],
    ) -> ContactRoutingPreferences:
        normalized_channel = _normalize_channel(channel)
        normalized_address = _normalize_address(channel_address, channel=normalized_channel)

        if normalized_address is None:
            return ContactRoutingPreferences(contact_id=None, normalized_address=None)

        contact: Optional[Contact] = None
        if normalized_channel == "email":
            contact = self.repository.find_by_email(org_id=self.org_id, email=channel_address)
        elif normalized_channel in PHONE_CHANNELS:
            contact = self.repository.find_by_sms(org_id=self.org_id, phone_number=channel_address)
        else:
            # Fallback for legacy callers without explicit channel.
            contact = self.repository.find_by_sms(org_id=self.org_id, phone_number=channel_address)
            if not contact:
                contact = self.repository.find_by_email(org_id=self.org_id, email=channel_address)

        if not contact:
            return ContactRoutingPreferences(
                contact_id=None,
                normalized_address=normalized_address,
            )

        opt_ins = (
            self.db.query(ContactChannelOptIn)
            .filter(ContactChannelOptIn.org_id == self.org_id)
            .filter(ContactChannelOptIn.contact_id == contact.id)
            .order_by(
                ContactChannelOptIn.channel.asc(),
                ContactChannelOptIn.channel_address.asc(),
                ContactChannelOptIn.version.desc(),
            )
            .all()
        )

        latest_by_key: Dict[Tuple[str, Optional[str]], ContactChannelOptIn] = {}
        for opt_in in opt_ins:
            channel_key = _normalize_channel(opt_in.channel) or ""
            address_key = _normalize_address(opt_in.channel_address, channel=channel_key)
            key = (channel_key, address_key)
            if key in latest_by_key:
                continue
            latest_by_key[key] = opt_in

        allowed_channels: Dict[str, Set[str]] = {}
        for (channel_key, address_key), opt_in in latest_by_key.items():
            if not channel_key:
                continue
            if opt_in.status == OptInStatusEnum.granted and address_key is not None:
                allowed_channels.setdefault(channel_key, set()).add(address_key)

        return ContactRoutingPreferences(
            contact_id=contact.id,
            normalized_address=normalized_address,
            allowed_channels=allowed_channels,
        )


class MultiChannelConsentResolver:
    """Facade that will evolve to resolve consent across multiple channels."""

    def __init__(self, db: Session, org_id: str) -> None:
        self._delegate = ContactPreferenceResolver(db, org_id)

    def resolve(
        self,
        *,
        channel: Optional[str],
        channel_address: Optional[str],
    ) -> ContactRoutingPreferences:
        # Current implementation is channel-agnostic; future iterations will
        # leverage the channel to select the appropriate lookup strategy.
        return self._delegate.load(channel=channel, channel_address=channel_address)
