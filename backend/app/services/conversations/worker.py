"""Background jobs for conversation metrics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import redis
from rq import Queue

from app.core.config import settings
from app.core.database import SessionLocal

from .metrics import ConversationMetricsService


def _queue() -> Queue:
    return Queue("default", connection=redis.from_url(settings.REDIS_URL))


def enqueue_sla_snapshot_rebuild(
    org_id: uuid.UUID,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    sla_target_seconds: int = 900,
) -> None:
    """Schedule a background task to rebuild SLA snapshots."""

    _queue().enqueue(
        rebuild_sla_snapshots,
        org_id=str(org_id),
        since=_serialize_datetime(since),
        until=_serialize_datetime(until),
        sla_target_seconds=sla_target_seconds,
    )


def rebuild_sla_snapshots(
    *,
    org_id: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    sla_target_seconds: int = 900,
) -> dict:
    """Rebuild SLA snapshots synchronously (RQ entry point)."""

    db = SessionLocal()
    try:
        service = ConversationMetricsService(
            db, sla_target_seconds=sla_target_seconds
        )
        org_uuid = uuid.UUID(str(org_id))
        since_dt = _parse_datetime(since) or datetime.now(timezone.utc)
        until_dt = _parse_datetime(until) if until else None
        service.rebuild_snapshots(org_id=org_uuid, since=since_dt, until=until_dt)
        db.commit()
        return {"status": "ok", "org_id": str(org_uuid)}
    finally:
        db.close()


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value in (None, ""):
        return None

    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
