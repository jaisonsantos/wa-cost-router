"""Rotinas de enfileiramento para sincronização incremental de CRM."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

import redis
from rq import Queue

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.crm import CRMIncrementalSyncService, SyncResult, build_default_registry

logger = logging.getLogger(__name__)

QUEUE_NAME = "crm_sync"
_LAST_ENQUEUE_KEY = "crm_sync:last_enqueued:{org_id}:{provider}"


def _redis_connection() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL)


def _queue(connection: Optional[redis.Redis] = None) -> Queue:
    connection = connection or _redis_connection()
    return Queue(QUEUE_NAME, connection=connection)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Optional[Union[str, datetime]]) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = str(value)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def enqueue_polling_cycle(
    *,
    org_id: Union[UUID, str],
    provider_slug: str,
    since: Optional[datetime] = None,
    page_size: Optional[int] = None,
    force: bool = False,
) -> bool:
    """Enfileira uma execução de polling, respeitando janela mínima entre tentativas."""

    connection = _redis_connection()
    key = _LAST_ENQUEUE_KEY.format(org_id=str(org_id), provider=provider_slug)
    now = time.time()
    interval = max(int(settings.CRM_POLLING_INTERVAL_SECONDS or 0), 0)

    last_enqueued_raw = connection.get(key)
    if not force and last_enqueued_raw:
        try:
            last_enqueued = float(last_enqueued_raw)
        except (TypeError, ValueError):  # pragma: no cover - defensivo
            last_enqueued = 0.0
        if now - last_enqueued < interval:
            logger.debug(
                "Skipping CRM polling enqueue due to interval guard",
                extra={
                    "event": "crm_sync_enqueue_skipped",
                    "provider_slug": provider_slug,
                    "org_id": str(org_id),
                },
            )
            return False

    job_kwargs = {
        "org_id": str(org_id),
        "provider_slug": provider_slug,
        "since": _serialize_datetime(since),
        "page_size": page_size,
    }

    queue = _queue(connection)
    queue.enqueue(run_polling_cycle, kwargs=job_kwargs)
    connection.set(key, str(now))

    logger.info(
        "CRM polling job enqueued",
        extra={
            "event": "crm_sync_enqueued",
            "provider_slug": provider_slug,
            "org_id": str(org_id),
        },
    )
    return True


def run_polling_cycle(
    *,
    org_id: str,
    provider_slug: str,
    since: Optional[Union[str, datetime]] = None,
    page_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Executa o polling incremental em background."""

    db = SessionLocal()
    try:
        service = CRMIncrementalSyncService(db, registry=build_default_registry())
        parsed_org_id = UUID(str(org_id))
        parsed_since = _parse_datetime(since)
        result = service.run_polling_cycle(
            org_id=parsed_org_id,
            provider_slug=provider_slug,
            since=parsed_since,
            page_size=page_size,
        )
    finally:
        db.close()

    return _serialize_result(result)


def _serialize_result(result: SyncResult) -> Dict[str, Any]:
    last_change = (
        result.last_change_at.astimezone(timezone.utc).isoformat()
        if result.last_change_at
        else None
    )
    return {
        "processed_contacts": result.processed_contacts,
        "has_more": result.has_more,
        "next_cursor": result.next_cursor,
        "last_change_at": last_change,
        "origin": result.origin,
    }


__all__ = [
    "enqueue_polling_cycle",
    "run_polling_cycle",
    "QUEUE_NAME",
]
