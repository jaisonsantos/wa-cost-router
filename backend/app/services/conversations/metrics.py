"""Aggregation utilities for SLA and backlog snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.models import Conversation, QueueEntry, SlaSnapshot


class ConversationMetricsService:
    """Builds aggregated SLA snapshots for reporting dashboards."""

    def __init__(self, db: Session, *, sla_target_seconds: int = 900) -> None:
        self.db = db
        self.sla_target_seconds = sla_target_seconds

    def rebuild_snapshots(
        self,
        *,
        org_id,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> List[SlaSnapshot]:
        """Recalculate snapshots for the provided window."""

        since = self._normalize_period_start(since)
        end_boundary = self._normalize_period_start(until) if until else self._normalize_period_start(
            datetime.now(timezone.utc)
        )
        end_boundary = end_boundary + timedelta(days=1)

        if since >= end_boundary:
            end_boundary = since + timedelta(days=1)

        (
            self.db.query(SlaSnapshot)
            .filter(SlaSnapshot.org_id == org_id)
            .filter(SlaSnapshot.period_start >= since)
            .filter(SlaSnapshot.period_start < end_boundary)
            .delete(synchronize_session=False)
        )
        self.db.flush()

        snapshots: List[SlaSnapshot] = []
        period_start = since

        while period_start < end_boundary:
            period_end = min(period_start + timedelta(days=1), end_boundary)

            channels = self._collect_channels(org_id=org_id, period_start=period_start, period_end=period_end)
            if not channels:
                period_start = period_end
                continue

            for channel in channels:
                snapshot = self._build_snapshot_for_channel(
                    org_id=org_id,
                    channel=channel,
                    period_start=period_start,
                    period_end=period_end,
                )
                snapshots.append(snapshot)
                self.db.add(snapshot)

            period_start = period_end

        self.db.flush()
        return snapshots

    def _build_snapshot_for_channel(
        self,
        *,
        org_id,
        channel: str,
        period_start: datetime,
        period_end: datetime,
    ) -> SlaSnapshot:
        conversations_query = (
            self.db.query(func.count(Conversation.id).label("count"))
            .filter(Conversation.org_id == org_id)
            .filter(Conversation.channel == channel)
        )

        opened_count = (
            conversations_query.filter(Conversation.opened_at >= period_start)
            .filter(Conversation.opened_at < period_end)
            .scalar()
            or 0
        )

        closed_count = (
            conversations_query.filter(Conversation.closed_at.isnot(None))
            .filter(Conversation.closed_at >= period_start)
            .filter(Conversation.closed_at < period_end)
            .scalar()
            or 0
        )

        latency_column = Conversation.first_response_latency_seconds
        latency_stats = (
            self.db.query(
                func.avg(latency_column).label("avg_latency"),
                func.count(latency_column).label("count_latency"),
                func.sum(
                    case(
                        (latency_column <= self.sla_target_seconds, 1),
                        else_=0,
                    )
                ).label("within_target"),
            )
            .filter(Conversation.org_id == org_id)
            .filter(Conversation.channel == channel)
            .filter(Conversation.opened_at >= period_start)
            .filter(Conversation.opened_at < period_end)
            .filter(latency_column.isnot(None))
            .one()
        )

        avg_latency = (
            int(round(latency_stats.avg_latency)) if latency_stats.avg_latency is not None else None
        )
        within_target = int(latency_stats.within_target or 0)

        backlog_open = (
            self.db.query(func.count(QueueEntry.id))
            .filter(QueueEntry.org_id == org_id)
            .filter(QueueEntry.channel == channel)
            .filter(QueueEntry.opened_at >= period_start)
            .filter(QueueEntry.opened_at < period_end)
            .scalar()
            or 0
        )

        backlog_closed = (
            self.db.query(func.count(QueueEntry.id))
            .filter(QueueEntry.org_id == org_id)
            .filter(QueueEntry.channel == channel)
            .filter(QueueEntry.closed_at.isnot(None))
            .filter(QueueEntry.closed_at >= period_start)
            .filter(QueueEntry.closed_at < period_end)
            .scalar()
            or 0
        )

        backlog_pending = (
            self.db.query(func.count(QueueEntry.id))
            .filter(QueueEntry.org_id == org_id)
            .filter(QueueEntry.channel == channel)
            .filter(QueueEntry.opened_at < period_end)
            .filter(
                or_(QueueEntry.closed_at.is_(None), QueueEntry.closed_at > period_end)
            )
            .scalar()
            or 0
        )

        return SlaSnapshot(
            org_id=org_id,
            channel=channel,
            period_start=period_start,
            period_end=period_end,
            sla_target_seconds=self.sla_target_seconds,
            conversations_opened=int(opened_count),
            conversations_closed=int(closed_count),
            first_response_avg_seconds=avg_latency,
            first_response_within_target=within_target,
            backlog_open=int(backlog_open),
            backlog_closed=int(backlog_closed),
            backlog_pending=int(backlog_pending),
        )

    def _collect_channels(
        self,
        *,
        org_id,
        period_start: datetime,
        period_end: datetime,
    ) -> List[str]:
        conversation_channels = (
            self.db.query(Conversation.channel)
            .filter(Conversation.org_id == org_id)
            .filter(Conversation.opened_at < period_end)
            .filter(
                or_(
                    Conversation.closed_at.is_(None),
                    Conversation.closed_at >= period_start,
                )
            )
            .distinct()
        )

        queue_channels = (
            self.db.query(QueueEntry.channel)
            .filter(QueueEntry.org_id == org_id)
            .filter(QueueEntry.opened_at < period_end)
            .filter(
                or_(
                    QueueEntry.closed_at.is_(None),
                    QueueEntry.closed_at >= period_start,
                )
            )
            .distinct()
        )

        channels = {row[0] for row in conversation_channels}
        channels.update(row[0] for row in queue_channels)

        return sorted(channel for channel in channels if channel)

    @staticmethod
    def _normalize_period_start(moment: Optional[datetime]) -> datetime:
        reference = moment or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return reference.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
