"""Serviços de manipulação de segmentos de contato."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import List, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import (
    Contact,
    ContactSegment,
    ContactSegmentMembership,
    ContactSegmentPolicy,
)


class ContactSegmentService:
    """Encapsula operações de persistência sobre segmentos e suas políticas."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Segment CRUD helpers
    def list_segments(self, org_id: UUID, *, limit: int | None = None, offset: int | None = None) -> List[ContactSegment]:
        query = (
            self.db.query(ContactSegment)
            .filter(ContactSegment.org_id == org_id)
            .order_by(ContactSegment.created_at.desc())
        )

        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        return query.all()

    def get_segment(self, org_id: UUID, segment_id: UUID) -> ContactSegment | None:
        return (
            self.db.query(ContactSegment)
            .filter(ContactSegment.org_id == org_id, ContactSegment.id == segment_id)
            .first()
        )

    def create_segment(self, org_id: UUID, **payload) -> ContactSegment:
        segment = ContactSegment(org_id=org_id, **payload)
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)
        return segment

    def update_segment(self, org_id: UUID, segment_id: UUID, **updates) -> ContactSegment | None:
        segment = self.get_segment(org_id=org_id, segment_id=segment_id)
        if segment is None:
            return None

        protected_fields = {"id", "org_id", "created_at"}
        for field, value in updates.items():
            if field in protected_fields:
                continue
            if hasattr(ContactSegment, field):
                setattr(segment, field, value)

        self.db.commit()
        self.db.refresh(segment)
        return segment

    def delete_segment(self, org_id: UUID, segment_id: UUID) -> bool:
        segment = self.get_segment(org_id=org_id, segment_id=segment_id)
        if segment is None:
            return False

        self.db.delete(segment)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Membership helpers
    def add_contacts_to_segment(
        self,
        org_id: UUID,
        segment_id: UUID,
        contact_ids: Sequence[UUID],
        *,
        membership_origin: str,
        source: str,
        source_metadata: dict | None,
    ) -> tuple[List[ContactSegmentMembership], List[UUID], List[UUID]]:
        segment = self.get_segment(org_id=org_id, segment_id=segment_id)
        if segment is None:
            return [], [], []

        if not contact_ids:
            return [], [], []

        contacts = (
            self.db.query(Contact)
            .filter(Contact.org_id == org_id, Contact.id.in_(contact_ids))
            .all()
        )
        found_ids = {contact.id for contact in contacts}
        missing = [contact_id for contact_id in contact_ids if contact_id not in found_ids]

        existing_memberships = (
            self.db.query(ContactSegmentMembership)
            .filter(
                ContactSegmentMembership.org_id == org_id,
                ContactSegmentMembership.segment_id == segment_id,
                ContactSegmentMembership.contact_id.in_(found_ids),
                ContactSegmentMembership.valid_to.is_(None),
            )
            .all()
        )
        already_associated = {membership.contact_id for membership in existing_memberships}

        new_memberships: List[ContactSegmentMembership] = []
        now = datetime.now(UTC)
        metadata = source_metadata or {}

        for contact in contacts:
            if contact.id in already_associated:
                continue
            membership = ContactSegmentMembership(
                org_id=org_id,
                contact_id=contact.id,
                segment_id=segment_id,
                membership_origin=membership_origin,
                valid_from=now,
                source=source,
                source_metadata=metadata,
            )
            self.db.add(membership)
            new_memberships.append(membership)

        if new_memberships:
            self.db.commit()
            for membership in new_memberships:
                self.db.refresh(membership)
        else:
            # Mesmo sem novos vínculos, garantir consistência.
            self.db.commit()

        return new_memberships, missing, list(already_associated)

    def remove_contact_from_segment(self, org_id: UUID, segment_id: UUID, contact_id: UUID) -> bool:
        membership = (
            self.db.query(ContactSegmentMembership)
            .filter(
                ContactSegmentMembership.org_id == org_id,
                ContactSegmentMembership.segment_id == segment_id,
                ContactSegmentMembership.contact_id == contact_id,
                ContactSegmentMembership.valid_to.is_(None),
            )
            .first()
        )

        if membership is None:
            return False

        membership.valid_to = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(membership)
        return True

    # ------------------------------------------------------------------
    # Policy helpers
    def upsert_policy(
        self,
        org_id: UUID,
        segment_id: UUID,
        *,
        limits: dict,
        opt_out: dict,
    ) -> ContactSegmentPolicy | None:
        segment = self.get_segment(org_id=org_id, segment_id=segment_id)
        if segment is None:
            return None

        policy = (
            self.db.query(ContactSegmentPolicy)
            .filter(
                ContactSegmentPolicy.org_id == org_id,
                ContactSegmentPolicy.segment_id == segment_id,
            )
            .first()
        )

        if policy is None:
            policy = ContactSegmentPolicy(
                org_id=org_id,
                segment_id=segment_id,
                limits=limits,
                opt_out=opt_out,
            )
            self.db.add(policy)
        else:
            policy.limits = limits
            policy.opt_out = opt_out

        self.db.commit()
        self.db.refresh(policy)
        return policy

    def get_policy(self, org_id: UUID, segment_id: UUID) -> ContactSegmentPolicy | None:
        return (
            self.db.query(ContactSegmentPolicy)
            .filter(
                ContactSegmentPolicy.org_id == org_id,
                ContactSegmentPolicy.segment_id == segment_id,
            )
            .first()
        )
