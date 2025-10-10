"""Lifecycle helpers for managing conversations and backlog entries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Conversation,
    ConversationStatusEnum,
    QueueEntry,
    QueueStatusEnum,
)


class ConversationLifecycleService:
    """Service responsible for opening, updating and closing conversations."""

    def __init__(self, db: Session, *, sla_target_seconds: int = 900) -> None:
        self.db = db
        self.sla_target_seconds = sla_target_seconds

    def handle_inbound(
        self,
        *,
        org_id,
        channel: str,
        channel_address: str,
        contact_id: Optional[object],
        occurred_at: datetime,
    ) -> Conversation:
        """Open or update a conversation after an inbound message."""

        conversation = self._get_active_conversation(
            org_id=org_id,
            channel=channel,
            channel_address=channel_address,
            contact_id=contact_id,
        )

        if conversation is None:
            conversation = Conversation(
                org_id=org_id,
                contact_id=contact_id,
                channel=channel,
                channel_address=channel_address,
                status=ConversationStatusEnum.waiting,
                opened_at=occurred_at,
                last_inbound_at=occurred_at,
            )
            self.db.add(conversation)
            self.db.flush([conversation])
        else:
            if contact_id and not conversation.contact_id:
                conversation.contact_id = contact_id
            conversation.last_inbound_at = occurred_at
            if conversation.opened_at is None:
                conversation.opened_at = occurred_at
            conversation.status = ConversationStatusEnum.waiting

        queue_entry = self._get_active_queue_entry(conversation)
        if queue_entry is None:
            queue_entry = QueueEntry(
                org_id=org_id,
                conversation_id=conversation.id,
                channel=channel,
                status=QueueStatusEnum.open,
                opened_at=occurred_at,
            )
            self.db.add(queue_entry)
        else:
            queue_entry.status = QueueStatusEnum.open
            if queue_entry.opened_at is None:
                queue_entry.opened_at = occurred_at

        conversation.updated_at = occurred_at
        return conversation

    def handle_outbound(
        self,
        *,
        org_id,
        channel: str,
        channel_address: str,
        contact_id: Optional[object],
        occurred_at: datetime,
    ) -> Conversation:
        """Close the backlog after an outbound response."""

        conversation = self._get_active_conversation(
            org_id=org_id,
            channel=channel,
            channel_address=channel_address,
            contact_id=contact_id,
        )

        if conversation is None:
            conversation = Conversation(
                org_id=org_id,
                contact_id=contact_id,
                channel=channel,
                channel_address=channel_address,
                status=ConversationStatusEnum.open,
                opened_at=occurred_at,
            )
            self.db.add(conversation)
            self.db.flush([conversation])

        if contact_id and not conversation.contact_id:
            conversation.contact_id = contact_id

        conversation.last_outbound_at = occurred_at
        if conversation.opened_at is None:
            conversation.opened_at = occurred_at

        queue_entry = self._get_active_queue_entry(conversation)
        if queue_entry and queue_entry.responded_at is None:
            queue_entry.responded_at = occurred_at
            queue_entry.first_response_latency_seconds = self._seconds_between(
                queue_entry.opened_at,
                occurred_at,
            )
            queue_entry.status = QueueStatusEnum.responded
            conversation.first_response_at = occurred_at
            conversation.first_response_latency_seconds = queue_entry.first_response_latency_seconds
        elif (
            conversation.first_response_at is None
            and conversation.last_inbound_at is not None
        ):
            conversation.first_response_at = occurred_at
            conversation.first_response_latency_seconds = self._seconds_between(
                conversation.last_inbound_at,
                occurred_at,
            )

        if queue_entry and queue_entry.closed_at is None:
            queue_entry.closed_at = occurred_at
            queue_entry.status = QueueStatusEnum.closed
            queue_entry.total_duration_seconds = self._seconds_between(
                queue_entry.opened_at,
                occurred_at,
            )

        conversation.closed_at = occurred_at
        conversation.status = ConversationStatusEnum.closed
        conversation.updated_at = occurred_at
        return conversation

    def _get_active_conversation(
        self,
        *,
        org_id,
        channel: str,
        channel_address: str,
        contact_id: Optional[object],
    ) -> Optional[Conversation]:
        base_query = (
            self.db.query(Conversation)
            .filter(Conversation.org_id == org_id)
            .filter(Conversation.channel == channel)
            .filter(Conversation.channel_address == channel_address)
            .filter(Conversation.status != ConversationStatusEnum.closed)
            .order_by(Conversation.opened_at.desc())
        )

        if contact_id:
            match = base_query.filter(Conversation.contact_id == contact_id).first()
            if match:
                return match

        return base_query.first()

    def _get_active_queue_entry(
        self, conversation: Conversation
    ) -> Optional[QueueEntry]:
        if conversation.id is None:
            return None

        return (
            self.db.query(QueueEntry)
            .filter(QueueEntry.conversation_id == conversation.id)
            .filter(QueueEntry.status != QueueStatusEnum.closed)
            .order_by(QueueEntry.opened_at.desc())
            .first()
        )

    @staticmethod
    def _seconds_between(
        start: Optional[datetime], end: Optional[datetime]
    ) -> Optional[int]:
        if start is None or end is None:
            return None

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        delta = end - start
        total = int(delta.total_seconds())
        return total if total >= 0 else 0
