import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.security import decrypt_credentials, decrypt_token, encrypt_token
from app.api.dependencies import get_current_user
from app.models.models import (
    WAConnection,
    MessageEvent,
    ContactChannelOptIn,
    ContactConsentAudit,
    OptInStatusEnum,
    Provider,
    ProviderCredential,
    IntegrationHealthStatus,
)
from app.services.contacts import ContactRepository, OptInRequestService
from app.services.conversations import ConversationLifecycleService
from app.services.routing.preferences import ContactPreferenceResolver
from app.services.provider_connectors import get_connector, run_health_check

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionCreate(BaseModel):
    business_id: str
    phone_id: str
    access_token: str
    webhook_verify_token: str
    webhook_secret: str


class HealthCheckSnapshot(BaseModel):
    healthy: bool
    status_code: Optional[str | int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    checked_at: Optional[datetime] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class IntegrationConnectionItem(BaseModel):
    id: str
    channel: str
    display_name: str
    status: str
    connected: bool
    has_credentials: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_health_check: Optional[HealthCheckSnapshot] = None


class ConnectionTestRequest(BaseModel):
    provider_id: Optional[UUID] = None


class ConnectionTestResponse(BaseModel):
    channel: str
    status: str
    healthy: bool
    status_code: Optional[str | int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    checked_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


DEFAULT_CONNECTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "whatsapp": {"display_name": "WhatsApp Business Cloud API"},
    "email": {"display_name": "Email (SendGrid)"},
    "sms": {"display_name": "SMS (Twilio)"},
    "telegram": {"display_name": "Telegram Bot"},
}


def _serialize_health(entry: Optional[IntegrationHealthStatus]) -> Optional[HealthCheckSnapshot]:
    if not entry:
        return None

    details = entry.details or {}
    return HealthCheckSnapshot(
        healthy=entry.healthy,
        status_code=entry.status_code,
        latency_ms=entry.latency_ms,
        error=entry.error,
        checked_at=entry.checked_at,
        details=details if isinstance(details, dict) else {"raw": details},
    )


def _resolve_connection_status(*, connected: bool, health: Optional[IntegrationHealthStatus]) -> str:
    if not connected:
        return "disconnected"
    if not health:
        return "unknown"
    if not health.healthy:
        return "error"
    if health.status_code and str(health.status_code) not in {"200", "201", "202"}:
        return "warning"
    return "healthy"


def _infer_channel(provider: Provider) -> str:
    type_hint = (provider.type or "").lower()
    name_hint = (provider.name or "").lower()
    if type_hint in {"sms", "twilio"} or name_hint in {"twilio"}:
        return "sms"
    if type_hint in {"email", "sendgrid"} or name_hint in {"sendgrid"}:
        return "email"
    if type_hint in {"whatsapp"}:
        return "whatsapp"
    return type_hint or name_hint or "unknown"


def _upsert_health_status(
    db: Session,
    *,
    org_id: UUID,
    channel: str,
    target_type: str,
    target_id: UUID,
    status: str,
    healthy: bool,
    status_code: Optional[str | int] = None,
    latency_ms: Optional[int] = None,
    error: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> IntegrationHealthStatus:
    now = datetime.now(timezone.utc)
    record = (
        db.query(IntegrationHealthStatus)
        .filter(
            IntegrationHealthStatus.target_type == target_type,
            IntegrationHealthStatus.target_id == target_id,
        )
        .first()
    )

    serialized_status_code = str(status_code) if status_code is not None else None
    safe_details = details or {}

    if record:
        record.org_id = org_id
        record.channel = channel
        record.status = status
        record.healthy = healthy
        record.status_code = serialized_status_code
        record.latency_ms = latency_ms
        record.error = error
        record.details = safe_details
        record.checked_at = now
        return record

    record = IntegrationHealthStatus(
        org_id=org_id,
        channel=channel,
        target_type=target_type,
        target_id=target_id,
        status=status,
        healthy=healthy,
        status_code=serialized_status_code,
        latency_ms=latency_ms,
        error=error,
        details=safe_details,
        checked_at=now,
    )
    db.add(record)
    return record

@router.get("/connections", response_model=List[IntegrationConnectionItem])
def list_connections(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = current_user["org_id"]

    health_entries = (
        db.query(IntegrationHealthStatus)
        .filter(IntegrationHealthStatus.org_id == org_id)
        .all()
    )
    health_lookup: Dict[tuple[str, str], IntegrationHealthStatus] = {
        (entry.target_type, str(entry.target_id)): entry for entry in health_entries
    }

    items: List[IntegrationConnectionItem] = []

    wa_connections = (
        db.query(WAConnection)
        .filter(WAConnection.org_id == org_id)
        .all()
    )

    for connection in wa_connections:
        health = health_lookup.get(("wa_connection", str(connection.id)))
        connected = connection.status == "active"
        metadata = {
            "business_id": connection.business_id,
            "phone_id": connection.phone_id,
            "status": connection.status,
            "connection_id": str(connection.id),
        }
        items.append(
            IntegrationConnectionItem(
                id=str(connection.id),
                channel="whatsapp",
                display_name=DEFAULT_CONNECTION_TEMPLATES["whatsapp"]["display_name"],
                status=_resolve_connection_status(connected=connected, health=health),
                connected=connected,
                has_credentials=True,
                metadata=metadata,
                last_health_check=_serialize_health(health),
            )
        )

    provider_credentials = (
        db.query(ProviderCredential)
        .filter(
            ProviderCredential.org_id == org_id,
            ProviderCredential.is_active.is_(True),
        )
        .all()
    )
    credential_by_provider = {credential.provider_id: credential for credential in provider_credentials}

    providers = db.query(Provider).filter(Provider.org_id == org_id).all()
    for provider in providers:
        channel = _infer_channel(provider)
        if channel == "whatsapp":
            continue

        has_credentials = provider.id in credential_by_provider
        health = health_lookup.get(("provider", str(provider.id)))
        connected = provider.status == "active" and has_credentials
        metadata: Dict[str, Any] = {
            "provider_name": provider.name,
            "provider_type": provider.type,
            "base_url": provider.base_url,
            "status": provider.status,
            "provider_id": str(provider.id),
        }
        if isinstance(provider.meta, dict):
            metadata["metadata"] = provider.meta

        items.append(
            IntegrationConnectionItem(
                id=str(provider.id),
                channel=channel or "unknown",
                display_name=(
                    provider.meta.get("display_name")
                    if isinstance(provider.meta, dict) and provider.meta.get("display_name")
                    else provider.name
                ),
                status=_resolve_connection_status(connected=connected, health=health),
                connected=connected,
                has_credentials=has_credentials,
                metadata=metadata,
                last_health_check=_serialize_health(health),
            )
        )

    existing_channels = {item.channel for item in items}
    for channel, template in DEFAULT_CONNECTION_TEMPLATES.items():
        if channel not in existing_channels:
            items.append(
                IntegrationConnectionItem(
                    id="",
                    channel=channel,
                    display_name=template["display_name"],
                    status="disconnected",
                    connected=False,
                    has_credentials=False,
                    metadata={},
                    last_health_check=None,
                )
            )

    order = {channel: index for index, channel in enumerate(DEFAULT_CONNECTION_TEMPLATES.keys())}
    items.sort(key=lambda item: (order.get(item.channel, len(order)), item.display_name.lower()))

    return items


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


@router.post("/{channel}/test", response_model=ConnectionTestResponse)
async def test_connection(
    channel: str,
    payload: Optional[ConnectionTestRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_channel = channel.lower()
    org_id = current_user["org_id"]
    request_data = payload or ConnectionTestRequest()

    if normalized_channel == "whatsapp":
        connection = (
            db.query(WAConnection)
            .filter(WAConnection.org_id == org_id)
            .first()
        )
        if not connection:
            raise HTTPException(status_code=404, detail="WhatsApp connection not configured")

        metadata = {
            "business_id": connection.business_id,
            "phone_id": connection.phone_id,
            "status": connection.status,
        }

        healthy = connection.status == "active"
        error: Optional[str] = None
        try:
            decrypt_token(connection.access_token_enc)
            decrypt_token(connection.webhook_secret_enc)
        except Exception as exc:  # noqa: BLE001 - propagate message to response
            healthy = False
            error = str(exc)

        status = "healthy" if healthy else "error"
        record = _upsert_health_status(
            db,
            org_id=org_id,
            channel="whatsapp",
            target_type="wa_connection",
            target_id=connection.id,
            status=status,
            healthy=healthy,
            error=error,
            details={"status": connection.status},
        )
        db.commit()
        db.refresh(record)

        return ConnectionTestResponse(
            channel="whatsapp",
            status=record.status,
            healthy=record.healthy,
            status_code=record.status_code,
            latency_ms=record.latency_ms,
            error=record.error,
            checked_at=record.checked_at,
            metadata=metadata,
        )

    if normalized_channel not in {"sms", "email"} and request_data.provider_id is None:
        raise HTTPException(status_code=400, detail=f"Channel '{channel}' is not supported")

    provider_candidates = db.query(Provider).filter(Provider.org_id == org_id).all()
    target_provider: Optional[Provider] = None

    if request_data.provider_id:
        for candidate in provider_candidates:
            if candidate.id == request_data.provider_id:
                target_provider = candidate
                break
        if not target_provider:
            raise HTTPException(status_code=404, detail="Provider not found for organization")
    else:
        for candidate in provider_candidates:
            if _infer_channel(candidate) == normalized_channel:
                target_provider = candidate
                break
        if not target_provider:
            raise HTTPException(status_code=404, detail=f"No provider configured for channel '{channel}'")

    credential = (
        db.query(ProviderCredential)
        .filter(
            ProviderCredential.org_id == org_id,
            ProviderCredential.provider_id == target_provider.id,
            ProviderCredential.is_active.is_(True),
        )
        .first()
    )
    if not credential:
        raise HTTPException(status_code=400, detail="Provider credentials not configured")

    try:
        credentials = decrypt_credentials(credential.credentials_encrypted)
    except Exception as exc:  # noqa: BLE001 - expose to client for remediation
        raise HTTPException(status_code=400, detail=f"Unable to decrypt credentials: {exc}") from exc

    try:
        health = await run_health_check(
            target_provider.name,
            credentials,
            target_provider.base_url,
            provider_type=target_provider.type,
        )
    except Exception as exc:  # noqa: BLE001
        health = {"healthy": False, "error": str(exc)}

    healthy = bool(health.get("healthy"))
    status_code = health.get("status_code")
    latency_ms = health.get("latency_ms")
    error = health.get("error")
    status = "healthy" if healthy else "error"

    sanitized_details = {
        key: value
        for key, value in health.items()
        if key not in {"error"}
    }

    record = _upsert_health_status(
        db,
        org_id=org_id,
        channel=normalized_channel,
        target_type="provider",
        target_id=target_provider.id,
        status=status,
        healthy=healthy,
        status_code=status_code,
        latency_ms=latency_ms,
        error=error,
        details=sanitized_details,
    )
    db.commit()
    db.refresh(record)

    metadata: Dict[str, Any] = {
        "provider_id": str(target_provider.id),
        "provider_name": target_provider.name,
        "provider_type": target_provider.type,
        "base_url": target_provider.base_url,
    }

    return ConnectionTestResponse(
        channel=normalized_channel,
        status=record.status,
        healthy=record.healthy,
        status_code=record.status_code,
        latency_ms=record.latency_ms,
        error=record.error,
        checked_at=record.checked_at,
        metadata=metadata,
    )

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
                    contact = contact_repository.find_by_sms(
                        org_id=connection.org_id, phone_number=channel_address
                    )
                    contact_id = contact.id if contact else None

                preferences = None
                has_consent = True
                if channel_address:
                    preferences = preference_resolver.load(
                        channel="whatsapp",
                        channel_address=channel_address,
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
                        channel="whatsapp",
                        channel_address=channel_address,
                        timestamp_provider=timestamp_provider,
                        delivery_status="received",
                        attributes=attributes,
                        contact_id=contact_id if contact_id and has_consent else None,
                    )
                )

    lifecycle_service = ConversationLifecycleService(db)
    for event in pending_events:
        db.add(event)
        if event.direction == "inbound" and event.channel_address:
            lifecycle_service.handle_inbound(
                org_id=event.org_id,
                channel=event.channel or "whatsapp",
                channel_address=event.channel_address,
                contact_id=event.contact_id,
                occurred_at=event.timestamp_provider,
            )

    db.commit()
    return {"status": "ok", "processed": len(pending_events)}

@router.post("/wa/test")
def test_send(current_user: dict = Depends(get_current_user)):
    return {"status": "ok", "message": "Test endpoint - no actual send"}
