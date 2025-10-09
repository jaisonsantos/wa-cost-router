"""Endpoints para confirmação de opt-ins via provedores externos."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.contacts import (
    OptInRequestInvalidStateError,
    OptInRequestNotFoundError,
    OptInRequestService,
    enqueue_opt_in_confirmation,
)

router = APIRouter()


class OptInWebhookPayload(BaseModel):
    """Estrutura esperada no webhook do provedor de opt-in."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    org_id: UUID
    status: str
    channel: str
    channel_address: str
    agent: str | None = "webhook"
    legal_basis: str | None = None
    captured_at: datetime | None = None
    evidence_uri: str | None = None
    proof_hash: str | None = None
    metadata: Dict[str, Any] | None = None
    request_ip: str | None = None


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def receive_opt_in_webhook(
    payload: OptInWebhookPayload,
    request: Request,
    async_process: bool = Query(False, alias="async"),
    x_opt_in_token: Optional[str] = Header(None, alias="X-Opt-In-Token"),
    db: Session = Depends(get_db),
):
    """Confirma solicitações de opt-in originadas de webhooks externos."""

    expected_token = settings.OPT_IN_WEBHOOK_TOKEN
    if expected_token and x_opt_in_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    normalized_status = payload.status.lower().strip()
    if normalized_status != "confirmed":
        return {"status": "ignored", "reason": f"unhandled status '{payload.status}'"}

    request_ip = payload.request_ip
    if not request_ip and request.client:
        request_ip = request.client.host

    if async_process:
        job_payload = payload.model_dump()
        job_payload["request_ip"] = request_ip
        enqueue_opt_in_confirmation(payload.request_id, job_payload)
        return {"status": "enqueued", "request_id": str(payload.request_id)}

    service = OptInRequestService(db)
    try:
        opt_in_request = service.confirm_from_webhook(
            org_id=payload.org_id,
            request_id=payload.request_id,
            channel=payload.channel,
            channel_address=payload.channel_address,
            agent=payload.agent or "webhook",
            legal_basis=payload.legal_basis,
            captured_at=payload.captured_at,
            evidence_uri=payload.evidence_uri,
            proof_hash=payload.proof_hash,
            metadata=payload.metadata,
            request_ip=request_ip,
        )
    except OptInRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OptInRequestInvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "confirmed",
        "request_id": str(opt_in_request.id),
        "opt_in_id": str(opt_in_request.opt_in_id) if opt_in_request.opt_in_id else None,
        "confirmed_at": opt_in_request.confirmed_at.isoformat() if opt_in_request.confirmed_at else None,
    }
