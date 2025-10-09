"""Tarefas assíncronas relacionadas a solicitações de opt-in."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from rq import Queue

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.contacts.opt_in_request_service import OptInRequestService


def _queue() -> Queue:
    return Queue("default", connection=redis.from_url(settings.REDIS_URL))


def enqueue_opt_in_confirmation(request_id: uuid.UUID, payload: Dict[str, Any]) -> None:
    """Enfileira processamento assíncrono de confirmação de opt-in."""

    _queue().enqueue(
        process_opt_in_confirmation,
        request_id=str(request_id),
        payload=payload,
    )


def process_opt_in_confirmation(*, request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Processa confirmação de opt-in recebida via webhook."""

    db = SessionLocal()
    try:
        service = OptInRequestService(db)
        request_uuid = uuid.UUID(str(request_id))
        org_uuid = uuid.UUID(str(payload["org_id"]))
        service.confirm_from_webhook(
            org_id=org_uuid,
            request_id=request_uuid,
            channel=payload["channel"],
            channel_address=payload["channel_address"],
            agent=payload.get("agent", "webhook"),
            legal_basis=payload.get("legal_basis"),
            captured_at=_parse_datetime(payload.get("captured_at")),
            evidence_uri=payload.get("evidence_uri"),
            proof_hash=payload.get("proof_hash"),
            metadata=payload.get("metadata"),
            request_ip=payload.get("request_ip"),
        )
        return {"status": "ok", "request_id": str(request_uuid)}
    finally:
        db.close()


def enqueue_due_opt_in_dispatch(limit: int = 50) -> None:
    """Enfileira processamento de retries pendentes."""

    _queue().enqueue(process_due_opt_in_requests, limit=limit)


def process_due_opt_in_requests(*, limit: int = 50) -> Dict[str, Any]:
    """Processa solicitações elegíveis para retry."""

    db = SessionLocal()
    try:
        service = OptInRequestService(db)
        processed = service.process_due_requests(limit=limit)
        return {
            "processed": [str(item.id) for item in processed],
            "count": len(processed),
        }
    finally:
        db.close()


def _parse_datetime(value: Optional[Any]) -> Optional[datetime]:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    raise ValueError("captured_at must be ISO string or datetime instance")
