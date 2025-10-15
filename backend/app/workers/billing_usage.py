"""RQ worker for syncing metered usage with Stripe."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import redis
from rq import Queue
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.billing.usage import BillingUsageService


logger = logging.getLogger(__name__)

QUEUE_NAME = "billing_usage"


def get_queue(connection: Optional[redis.Redis] = None) -> Queue:
    conn = connection or redis.from_url(settings.REDIS_URL)
    return Queue(QUEUE_NAME, connection=conn)


def enqueue_billing_usage_sync(*, limit: int | None = None) -> str:
    job = get_queue().enqueue(
        process_billing_usage_sync,
        kwargs={"limit": limit},
    )
    return job.id


def process_billing_usage_sync(
    *,
    limit: int | None = None,
    now: datetime | None = None,
    db_session: Session | None = None,
) -> dict[str, int | str]:
    if not settings.BILLING_USAGE_SYNC_ENABLED:
        logger.info("Billing usage sync disabled via BILLING_USAGE_SYNC_ENABLED flag")
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "status": "disabled"}

    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True

    try:
        service = BillingUsageService(db_session)
        if not service.sync_enabled:
            logger.info(
                "Billing usage sync disabled (flag or missing Stripe secret)",
                extra={"event": "billing_usage_disabled"},
            )
            return {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "status": "disabled",
            }

        batch_limit = limit or settings.BILLING_USAGE_BATCH_SIZE
        result = service.sync_due_windows(
            now=now or datetime.now(timezone.utc),
            limit=batch_limit,
        )
        payload = result.to_dict()
        payload["status"] = "completed"
        logger.info(
            "Billing usage sync batch finished",
            extra={"event": "billing_usage_batch", **payload},
        )
        return payload
    finally:
        if close_session:
            db_session.close()


__all__ = [
    "enqueue_billing_usage_sync",
    "get_queue",
    "process_billing_usage_sync",
]
