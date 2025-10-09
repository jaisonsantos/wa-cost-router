"""Repositório para operações com contatos e consentimentos."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Union

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    Contact,
    ContactChannelOptIn,
    ContactConsentAudit,
    ContactSegment,
    ContactSegmentMembership,
    ContactStatusEnum,
    OptInStatusEnum,
)
from app.services.contacts.sanitization import sanitize_contact_payload


def _normalize_sequence(value: Optional[Union[Sequence, Iterable, str, int]]) -> List:
    """Normaliza o valor recebido para uma lista simples."""

    if value is None:
        return []

    allowed_iterables = (list, tuple, set, frozenset)
    if isinstance(value, allowed_iterables):
        return list(value)

    return [value]


class ContactRepository:
    """Encapsula operações de persistência sobre o catálogo de contatos."""

    def __init__(self, db: Session):
        self.db = db

    # CRUD -----------------------------------------------------------------
    def create_contact(self, **payload) -> Contact:
        sanitized_payload = sanitize_contact_payload(payload)
        contact = Contact(**sanitized_payload)
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def get_contact(self, org_id, contact_id) -> Optional[Contact]:
        return (
            self.db.query(Contact)
            .filter(Contact.org_id == org_id, Contact.id == contact_id)
            .first()
        )

    def update_contact(self, org_id, contact_id, **updates) -> Optional[Contact]:
        contact = self.get_contact(org_id=org_id, contact_id=contact_id)
        if not contact:
            return None

        protected_fields = {"id", "org_id", "created_at"}
        sanitized_updates = sanitize_contact_payload(updates)
        for field, value in sanitized_updates.items():
            if field in protected_fields:
                continue
            if hasattr(Contact, field):
                setattr(contact, field, value)

        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete_contact(self, org_id, contact_id) -> bool:
        contact = self.get_contact(org_id=org_id, contact_id=contact_id)
        if not contact:
            return False

        self.db.delete(contact)
        self.db.commit()
        return True

    # Queries --------------------------------------------------------------
    def list_contacts(
        self,
        org_id,
        *,
        status: Optional[ContactStatusEnum] = None,
        segment_ids: Optional[Union[Sequence, Iterable]] = None,
        segment_slugs: Optional[Union[Sequence, Iterable]] = None,
        channel: Optional[str] = None,
        channel_status: Optional[Union[OptInStatusEnum, Sequence[OptInStatusEnum]]] = None,
        channel_address: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Contact]:
        """Retorna contatos com filtros opcionais por segmento e canal."""

        query = self.db.query(Contact).filter(Contact.org_id == org_id)

        if status is not None:
            query = query.filter(Contact.status == status)

        normalized_segment_ids = _normalize_sequence(segment_ids)
        normalized_segment_slugs = _normalize_sequence(segment_slugs)

        if normalized_segment_ids or normalized_segment_slugs:
            query = query.join(Contact.segment_memberships)

            if normalized_segment_ids:
                query = query.filter(
                    ContactSegmentMembership.segment_id.in_(normalized_segment_ids)
                )

            if normalized_segment_slugs:
                query = query.join(ContactSegmentMembership.segment).filter(
                    ContactSegment.slug.in_(normalized_segment_slugs)
                )

        needs_channel_join = any(
            value is not None
            for value in (channel, channel_status, channel_address)
        )

        if needs_channel_join:
            query = query.join(Contact.channel_opt_ins)

            if channel is not None:
                query = query.filter(ContactChannelOptIn.channel == channel)

            if channel_status is not None:
                normalized_status = _normalize_sequence(channel_status)
                if normalized_status:
                    query = query.filter(ContactChannelOptIn.status.in_(normalized_status))

            if channel_address is not None:
                query = query.filter(
                    ContactChannelOptIn.channel_address == channel_address
                )

        ranking_query = query.with_entities(
            Contact.id.label("contact_id"),
            Contact.created_at.label("created_at"),
            func.row_number()
            .over(
                partition_by=Contact.id,
                order_by=(Contact.created_at.desc(), Contact.id.desc()),
            )
            .label("row_number"),
        )

        ranked_subquery = ranking_query.subquery()

        windowed_query = (
            self.db.query(ranked_subquery.c.contact_id, ranked_subquery.c.created_at)
            .filter(ranked_subquery.c.row_number == 1)
            .order_by(
                ranked_subquery.c.created_at.desc(),
                ranked_subquery.c.contact_id.desc(),
            )
        )

        if offset:
            windowed_query = windowed_query.offset(offset)

        if limit:
            windowed_query = windowed_query.limit(limit)

        ordered_rows = windowed_query.all()

        if not ordered_rows:
            return []

        ordered_ids = [row.contact_id for row in ordered_rows]
        ordering = case({contact_id: index for index, contact_id in enumerate(ordered_ids)}, value=Contact.id)

        return (
            self.db.query(Contact)
            .filter(Contact.id.in_(ordered_ids))
            .order_by(ordering)
            .all()
        )

    def list_consent_history(
        self,
        *,
        org_id,
        contact_id,
        channel: Optional[str] = None,
        channel_address: Optional[str] = None,
    ) -> List[ContactConsentAudit]:
        """Retorna eventos de auditoria de consentimento para um contato."""

        query = (
            self.db.query(ContactConsentAudit)
            .options(joinedload(ContactConsentAudit.opt_in))
            .filter(
                ContactConsentAudit.org_id == org_id,
                ContactConsentAudit.contact_id == contact_id,
            )
        )

        if channel is not None:
            query = query.filter(ContactConsentAudit.channel == channel)

        if channel_address is not None:
            query = query.filter(ContactConsentAudit.channel_address == channel_address)

        return (
            query.order_by(
                ContactConsentAudit.recorded_at.desc(),
                ContactConsentAudit.created_at.desc(),
            )
            .all()
        )

