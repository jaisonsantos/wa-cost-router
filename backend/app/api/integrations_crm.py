"""CRM integration endpoints (webhooks and fallback polling)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.crm import (
    CRMIncrementalSyncService,
    CredentialsNotConfiguredError,
    ProviderNotConfiguredError,
    ProviderNotRegisteredError,
    SyncResult,
    build_default_registry,
)
from app.services.crm.exceptions import ProviderSyncError

logger = logging.getLogger(__name__)

router = APIRouter()
_registry = build_default_registry()


class PollRequest(BaseModel):
    since: Optional[datetime] = None
    page_size: Optional[int] = Field(default=None, ge=1)


def _compute_signature(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return digest


def _verify_signature(*, secret: str, payload: bytes, provided: Optional[str]) -> bool:
    if not secret or not provided:
        return False
    expected = _compute_signature(secret, payload)
    return hmac.compare_digest(expected, provided)


def _serialize_sync_result(result: SyncResult) -> Dict[str, Any]:
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


def _get_crm_service(db: Session) -> CRMIncrementalSyncService:
    return CRMIncrementalSyncService(db, registry=_registry)


@router.post("/{slug}/webhook", status_code=status.HTTP_200_OK)
async def handle_crm_webhook(
    slug: str,
    request: Request,
    *,
    org_id: UUID = Query(..., description="Identificador da organização proprietária."),
    db: Session = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("X-HubSpot-Signature")

    if not _verify_signature(
        secret=settings.CRM_WEBHOOK_SECRET,
        payload=body,
        provided=signature,
    ):
        logger.info(
            "CRM webhook rejected due to invalid signature",
            extra={"provider_slug": slug, "org_id": str(org_id)},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        logger.warning(
            "CRM webhook received invalid JSON payload",
            extra={"provider_slug": slug, "org_id": str(org_id)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from exc

    service = _get_crm_service(db)
    try:
        result = service.handle_webhook_event(
            org_id=org_id,
            provider_slug=slug,
            payload=payload,
        )
    except ProviderNotRegisteredError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown CRM provider")
    except ProviderNotConfiguredError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not configured for organization")
    except CredentialsNotConfiguredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider credentials not configured")
    except ProviderSyncError as exc:
        logger.exception(
            "CRM webhook processing failed",
            extra={"provider_slug": slug, "org_id": str(org_id)},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _serialize_sync_result(result)


@router.post("/{slug}/poll", status_code=status.HTTP_200_OK)
def trigger_crm_poll(
    slug: str,
    payload: PollRequest = Body(default_factory=PollRequest),
    *,
    org_id: UUID = Query(..., description="Identificador da organização proprietária."),
    db: Session = Depends(get_db),
):
    service = _get_crm_service(db)
    try:
        result = service.run_polling_cycle(
            org_id=org_id,
            provider_slug=slug,
            since=payload.since,
            page_size=payload.page_size,
        )
    except ProviderNotRegisteredError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown CRM provider")
    except ProviderNotConfiguredError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not configured for organization")
    except CredentialsNotConfiguredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider credentials not configured")
    except ProviderSyncError as exc:
        logger.exception(
            "CRM polling cycle failed",
            extra={"provider_slug": slug, "org_id": str(org_id)},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _serialize_sync_result(result)
