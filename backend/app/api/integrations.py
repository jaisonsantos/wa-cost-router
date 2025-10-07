import hashlib
import hmac
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import logging
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.security import decrypt_token, encrypt_token
from app.api.dependencies import get_current_user
from app.models.models import WAConnection, MessageEvent

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionCreate(BaseModel):
    business_id: str
    phone_id: str
    access_token: str
    webhook_verify_token: str
    webhook_secret: str

@router.post("/wa/connections")
def create_connection(
    data: ConnectionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = current_user["org_id"]
    encrypted_token = encrypt_token(data.access_token)
    encrypted_secret = encrypt_token(data.webhook_secret)

    existing = (
        db.query(WAConnection)
        .filter(
            WAConnection.org_id == org_id,
            WAConnection.phone_id == data.phone_id,
        )
        .first()
    )

    conflict_query = db.query(WAConnection).filter(
        WAConnection.webhook_verify_token == data.webhook_verify_token
    )
    if existing:
        conflict_query = conflict_query.filter(WAConnection.id != existing.id)
    conflict_connection = conflict_query.first()
    if conflict_connection:
        raise HTTPException(
            status_code=400,
            detail="Webhook verify token already in use",
        )

    if existing:
        connection = existing
        connection.business_id = data.business_id
        connection.phone_id = data.phone_id
        connection.access_token_enc = encrypted_token
        connection.webhook_verify_token = data.webhook_verify_token
        connection.webhook_secret_enc = encrypted_secret
        connection.status = "active"
    else:
        connection = WAConnection(
            org_id=org_id,
            business_id=data.business_id,
            phone_id=data.phone_id,
            access_token_enc=encrypted_token,
            webhook_verify_token=data.webhook_verify_token,
            webhook_secret_enc=encrypted_secret,
            status="active"
        )
        db.add(connection)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.exception(
            "Failed to persist WA connection due to integrity error",
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(
            status_code=400,
            detail="Unable to save WhatsApp connection",
        )

    db.refresh(connection)
    return {"id": str(connection.id), "status": connection.status}

@router.get("/wa/webhook")
def webhook_verify(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
    db: Session = Depends(get_db),
):
    if mode != "subscribe":
        raise HTTPException(status_code=403, detail="Verification failed")

    connection_exists = (
        db.query(WAConnection.id)
        .filter(
            WAConnection.webhook_verify_token == token,
            WAConnection.status == "active",
        )
        .first()
    )

    if not connection_exists:
        raise HTTPException(status_code=403, detail="Verification failed")

    return PlainTextResponse(content=str(challenge))

@router.post("/wa/webhook")
async def webhook_receive(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    try:
        body = json.loads(body_text or "{}")
    except json.JSONDecodeError:
        logger.warning(
            "Invalid webhook payload received", extra={"message_event_ids": []}
        )
        raise HTTPException(status_code=400, detail="Invalid payload")

    message_event_ids: List[str] = []
    phone_number_id = None

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {}) or {}

            if not phone_number_id:
                phone_number_id = metadata.get("phone_number_id")

            for msg in value.get("messages", []):
                provider_id = msg.get("id")
                if provider_id:
                    message_event_ids.append(provider_id)

    if not phone_number_id:
        if message_event_ids:
            logger.warning(
                "Webhook without phone_number_id metadata",
                extra={"message_event_ids": message_event_ids},
            )
        return {"status": "ignored", "processed": 0}

    connection = (
        db.query(WAConnection)
        .filter(
            WAConnection.phone_id == phone_number_id,
            WAConnection.status == "active",
        )
        .first()
    )

    if not connection:
        if message_event_ids:
            logger.warning(
                "Webhook received for unknown phone_number_id",
                extra={"message_event_ids": message_event_ids},
            )
        return {"status": "ignored", "processed": 0}

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        logger.warning(
            "Missing or malformed webhook signature",
            extra={"message_event_ids": message_event_ids},
        )
        raise HTTPException(status_code=403, detail="Invalid signature")

    secret = decrypt_token(connection.webhook_secret_enc)
    provided_signature = signature_header.split("=", 1)[1]
    expected_signature = hmac.new(
        secret.encode("utf-8"), raw_body or b"", hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(provided_signature, expected_signature):
        logger.warning(
            "Invalid webhook signature",
            extra={"message_event_ids": message_event_ids},
        )
        raise HTTPException(status_code=403, detail="Invalid signature")

    processed = 0
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                provider_id = msg.get("id")
                if not provider_id:
                    continue

                # Check idempotency
                existing = db.query(MessageEvent).filter(
                    MessageEvent.provider_event_id == provider_id
                ).first()
                if existing:
                    continue

                event = MessageEvent(
                    org_id=connection.org_id,
                    connection_id=connection.id,
                    provider_event_id=provider_id,
                    direction="inbound",
                    timestamp_provider=datetime.utcnow(),
                    delivery_status="received",
                    attributes=msg,
                )
                db.add(event)
                processed += 1

    db.commit()
    return {"status": "ok", "processed": processed}

@router.post("/wa/test")
def test_send(current_user: dict = Depends(get_current_user)):
    return {"status": "ok", "message": "Test endpoint - no actual send"}
