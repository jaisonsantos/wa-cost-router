import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.security import decrypt_token, encrypt_token
from app.api.dependencies import get_current_user
from app.models.models import (
    WAConnection,
    MessageEvent,
    ContactChannelOptIn,
    ContactConsentAudit,
    OptInStatusEnum,
)
from app.services.contacts import ContactRepository, OptInRequestService
from app.services.routing.preferences import ContactPreferenceResolver

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

    conflict_query = (
        db.query(WAConnection)
        .filter(
            WAConnection.org_id == org_id,
            WAConnection.webhook_verify_token == data.webhook_verify_token,
        )
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

MASK_TOKEN = "***redacted***"
TEXT_MASK_KEYS = {
    "body",
    "caption",
    "description",
    "message",
    "text",
}
IDENTIFIER_MASK_KEYS = {
    "display_phone_number",
    "email",
    "from",
    "name",
    "phone_number",
    "wa_id",
}
FULL_MASK_KEYS = {"contacts", "profile"}


def _mask_message_payload(value, parent_key: Optional[str] = None):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FULL_MASK_KEYS:
                sanitized[key] = MASK_TOKEN
                continue
            if lowered in IDENTIFIER_MASK_KEYS and isinstance(item, str):
                sanitized[key] = MASK_TOKEN
                continue
            sanitized[key] = _mask_message_payload(item, parent_key=lowered)
        return sanitized
    if isinstance(value, list):
        return [_mask_message_payload(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        if parent_key in TEXT_MASK_KEYS or parent_key in IDENTIFIER_MASK_KEYS:
            return MASK_TOKEN
    return value


def _parse_provider_timestamp(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)
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
    if signature_header.startswith("sha256="):
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
            return {"status": "ignored", "processed": 0}
    else:
        logger.warning(
            "Missing or malformed webhook signature",
            extra={"message_event_ids": message_event_ids},
        )
        return {"status": "ignored", "processed": 0}

    contact_repository = ContactRepository(db)
    preference_resolver = ContactPreferenceResolver(db, connection.org_id)
    opt_in_service: Optional[OptInRequestService] = None
    pending_events: List[MessageEvent] = []

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                provider_id = msg.get("id")
                if not provider_id:
                    continue

                existing = (
                    db.query(MessageEvent)
                    .filter(MessageEvent.provider_event_id == provider_id)
                    .first()
                )
                if existing:
                    continue

                channel_address = msg.get("from")
                contact = None
                contact_id = None

                if channel_address:
                    contact = contact_repository.find_by_phone(
                        org_id=connection.org_id, phone_number=channel_address
                    )
                    contact_id = contact.id if contact else None

                preferences = None
                has_consent = True
                if channel_address:
                    preferences = preference_resolver.load(
                        channel_address=channel_address
                    )
                    if contact_id is None and preferences.contact_id is not None:
                        contact_id = preferences.contact_id
                    has_consent = preferences.is_channel_allowed(
                        "whatsapp", channel_address
                    )
                    if contact_id and not has_consent:
                        normalized_incoming = ContactRepository._normalize_phone(
                            channel_address
                        )
                        if normalized_incoming:
                            active_opt_ins = (
                                db.query(ContactChannelOptIn)
                                .filter(ContactChannelOptIn.contact_id == contact_id)
                                .filter(ContactChannelOptIn.org_id == connection.org_id)
                                .filter(ContactChannelOptIn.channel == "whatsapp")
                                .filter(
                                    ContactChannelOptIn.status
                                    == OptInStatusEnum.granted
                                )
                                .all()
                            )
                            for opt_in_record in active_opt_ins:
                                normalized_opt_in = (
                                    ContactRepository._normalize_phone(
                                        opt_in_record.channel_address
                                    )
                                )
                                if (
                                    normalized_opt_in
                                    and normalized_opt_in == normalized_incoming
                                ):
                                    has_consent = True
                                    break

                if channel_address and not has_consent:
                    if contact_id:
                        denial_hash = hashlib.sha256(
                            f"denied:{provider_id}".encode("utf-8")
                        ).hexdigest()
                        existing_audit = (
                            db.query(ContactConsentAudit)
                            .filter(ContactConsentAudit.org_id == connection.org_id)
                            .filter(ContactConsentAudit.contact_id == contact_id)
                            .filter(ContactConsentAudit.proof_hash == denial_hash)
                            .first()
                        )

                        if not existing_audit:
                            audit_entry = ContactConsentAudit(
                                org_id=connection.org_id,
                                contact_id=contact_id,
                                opt_in_id=None,
                                channel="whatsapp",
                                channel_address=channel_address,
                                status=OptInStatusEnum.revoked,
                                source="webhook",
                                agent="wa_webhook",
                                request_ip=getattr(request.client, "host", None),
                                proof_hash=denial_hash,
                                context={
                                    "reason": "opt_in_missing",
                                    "provider_event_id": provider_id,
                                },
                            )
                            db.add(audit_entry)
                            db.commit()
                        if opt_in_service is None:
                            opt_in_service = OptInRequestService(db)
                        try:
                            opt_in_service.enqueue_request(
                                org_id=connection.org_id,
                                contact_id=contact_id,
                                requested_channel="whatsapp",
                                requested_address=channel_address,
                                dispatch_immediately=False,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to enqueue opt-in request after denied inbound message",
                                extra={
                                    "org_id": str(connection.org_id),
                                    "provider_event_id": provider_id,
                                },
                            )
                    else:
                        logger.warning(
                            "Inbound message denied because contact has no consent or record",
                            extra={
                                "provider_event_id": provider_id,
                                "org_id": str(connection.org_id),
                            },
                        )
                    return {"status": "denied"}

                timestamp_provider = _parse_provider_timestamp(msg.get("timestamp"))
                attributes = _mask_message_payload(msg)

                pending_events.append(
                    MessageEvent(
                        org_id=connection.org_id,
                        connection_id=connection.id,
                        provider_event_id=provider_id,
                        direction="inbound",
                        timestamp_provider=timestamp_provider,
                        delivery_status="received",
                        attributes=attributes,
                        contact_id=contact_id if contact_id and has_consent else None,
                    )
                )

    for event in pending_events:
        db.add(event)

    db.commit()
    return {"status": "ok", "processed": len(pending_events)}

@router.post("/wa/test")
def test_send(current_user: dict = Depends(get_current_user)):
    return {"status": "ok", "message": "Test endpoint - no actual send"}
