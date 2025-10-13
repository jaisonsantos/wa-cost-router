from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Dict, Optional

import redis
from rq import Queue
from sqlalchemy.orm import Session

from app.core.circuit_breaker import get_circuit_breaker_store
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import MessageJob
from app.services.messages.delivery import (
    DeliveryContext,
    MessageDeliveryService,
    MESSAGES_SEND_COUNTER,
)


logger = logging.getLogger(__name__)

QUEUE_NAME = "message_send"


def get_queue(connection: Optional[redis.Redis] = None) -> Queue:
    conn = connection or redis.from_url(settings.REDIS_URL)
    return Queue(QUEUE_NAME, connection=conn)


def enqueue_message_delivery(context: Dict[str, Any]) -> str:
    delivery_context = DeliveryContext.from_payload(context)
    job = get_queue().enqueue(process_message_send, context=delivery_context.to_payload())
    return job.id


def process_message_send(
    *,
    context: Dict[str, Any],
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True

    try:
        delivery_context = DeliveryContext.from_payload(context)
        circuit_breaker = get_circuit_breaker_store()
        service = MessageDeliveryService(db_session, circuit_breaker)

        result = _run_coroutine(service.deliver(delivery_context))

        channel = result.channel or _load_job_channel(db_session, result.job_id)
        provider = result.provider_name or "none"

        try:
            MESSAGES_SEND_COUNTER.labels(
                status=result.status,
                provider=provider,
                channel=channel or "unknown",
            ).inc()
        except Exception:  # pragma: no cover - metrics must not break worker
            logger.exception(
                "Failed to record messages_send_total metric",
                extra={
                    "event": "metrics_error",
                    "metric": "messages_send_total",
                    "provider": provider,
                    "channel": channel,
                },
            )

        return {
            "job_id": result.job_id,
            "status": result.status,
            "provider": result.provider_name,
            "message": result.message,
            "channel": channel,
        }
    finally:
        if close_session:
            db_session.close()


def _load_job_channel(db: Session, job_id: str) -> Optional[str]:
    try:
        job_uuid = uuid.UUID(str(job_id))
    except (TypeError, ValueError):
        logger.warning("Unable to parse job id %r for channel lookup", job_id)
        return None

    job = db.get(MessageJob, job_uuid)
    if job is None:
        return None
    return job.channel


def _run_coroutine(coro: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


__all__ = [
    "enqueue_message_delivery",
    "get_queue",
    "process_message_send",
]

