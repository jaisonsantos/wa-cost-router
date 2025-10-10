"""SMS integrations webhook handlers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decrypt_credentials
from app.models.models import (
    Contact,
    ContactChannelOptIn,
    MessageEvent,
    OptInStatusEnum,
    Provider,
    ProviderCredential,
)
from app.services.contacts import ContactRepository, OptInRequestService
from app.services.routing.preferences import ContactPreferenceResolver

logger = logging.getLogger(__name__)

router = APIRouter()

MASK_TOKEN = "***redacted***"
BODY_MASK_KEYS = {"body", "message", "text"}
IDENTIFIER_MASK_KEYS = {"from", "to", "phonenumber", "phonenumber_sid"}


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    return ContactRepository._normalize_phone(value)


def _mask_payload(pairs: Iterable[Tuple[str, str]]) -> Dict[str, str]:
    masked: Dict[str, str] = {}
    for key, value in pairs:
        lowered = key.lower()
        if lowered in BODY_MASK_KEYS:
            masked[key] = MASK_TOKEN
        elif lowered in IDENTIFIER_MASK_KEYS:
            masked[key] = MASK_TOKEN
        else:
            masked[key] = value
    return masked


def _parse_timestamp(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    sanitized = value.strip()
    if not sanitized:
        return datetime.now(timezone.utc)

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(sanitized, fmt)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(sanitized.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        logger.debug("Unable to parse timestamp %r; defaulting to now", value)
        return datetime.now(timezone.utc)


def _compute_twilio_signature(
    *, auth_token: str, url: str, params: Iterable[Tuple[str, str]]
) -> str:
    sorted_params = sorted(params, key=lambda item: item[0])
    payload = url
    for key, value in sorted_params:
        payload += key + value

    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _match_provider_for_destination(
    *,
    db: Session,
    to_number: Optional[str],
    messaging_service_sid: Optional[str],
) -> Optional[Tuple[Provider, Dict[str, str]]]:
    normalized_to = _normalize_phone(to_number)
    requested_service_sid = (messaging_service_sid or "").strip()

    candidates: List[Tuple[Provider, ProviderCredential]] = (
        db.query(Provider, ProviderCredential)
        .join(ProviderCredential, ProviderCredential.provider_id == Provider.id)
        .filter(ProviderCredential.is_active.is_(True))
        .filter(Provider.org_id == ProviderCredential.org_id)
        .filter(Provider.type.in_(["sms", "twilio"]))
        .all()
    )

    for provider, credential in candidates:
        try:
            credentials = decrypt_credentials(credential.credentials_encrypted)
        except Exception:  # pragma: no cover - defensive decoding guard
            logger.exception(
                "Failed to decrypt credentials for provider", extra={"provider_id": str(provider.id)}
            )
            continue

        declared_numbers: List[str] = []
        primary_number = credentials.get("from_number")
        if primary_number:
            declared_numbers.append(primary_number)

        additional_numbers = credentials.get("numbers") or []
        if isinstance(additional_numbers, list):
            for number in additional_numbers:
                if isinstance(number, str):
                    declared_numbers.append(number)

        meta = provider.meta or {}
        channels_meta = meta.get("channels") if isinstance(meta, dict) else {}
        sms_meta = channels_meta.get("sms") if isinstance(channels_meta, dict) else {}
        if isinstance(sms_meta, dict):
            inbound_numbers = sms_meta.get("inbound_numbers") or []
            if isinstance(inbound_numbers, list):
                for number in inbound_numbers:
                    if isinstance(number, str):
                        declared_numbers.append(number)

        normalized_declared = {
            value
            for value in (
                _normalize_phone(number)
                for number in declared_numbers
            )
            if value is not None
        }

        credential_service_sid = (credentials.get("messaging_service_sid") or "").strip()

        if normalized_to and normalized_to in normalized_declared:
            return provider, credentials

        if requested_service_sid and credential_service_sid:
            if requested_service_sid == credential_service_sid:
                return provider, credentials

    return None


def _has_active_consent(
    *,
    db: Session,
    org_id,
    contact_id,
    channel: str,
    incoming_address: str,
) -> bool:
    normalized_incoming = _normalize_phone(incoming_address)
    if not normalized_incoming:
        return False

    active_opt_ins = (
        db.query(ContactChannelOptIn)
        .filter(ContactChannelOptIn.contact_id == contact_id)
        .filter(ContactChannelOptIn.org_id == org_id)
        .filter(ContactChannelOptIn.channel == channel)
        .filter(ContactChannelOptIn.status == OptInStatusEnum.granted)
        .all()
    )

    for opt_in in active_opt_ins:
        normalized_opt_in = _normalize_phone(opt_in.channel_address)
        if normalized_opt_in and normalized_opt_in == normalized_incoming:
            return True
    return False


@router.post("/webhook")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_items = list(form.multi_items())
    payload_dict = {key: value for key, value in form_items}

    to_number = payload_dict.get("To")
    from_number = payload_dict.get("From")
    message_sid = payload_dict.get("MessageSid")
    messaging_service_sid = payload_dict.get("MessagingServiceSid")

    if not message_sid:
        raise HTTPException(status_code=400, detail="Missing MessageSid")

    provider_match = _match_provider_for_destination(
        db=db, to_number=to_number, messaging_service_sid=messaging_service_sid
    )
    if not provider_match:
        logger.warning(
            "SMS webhook received for unknown destination", extra={"to": to_number, "sid": message_sid}
        )
        return {"status": "ignored", "reason": "unknown_destination"}

    provider, credentials = provider_match
    auth_token = credentials.get("auth_token")
    if not auth_token:
        logger.warning(
            "SMS webhook ignored because credentials lack auth_token",
            extra={"provider_id": str(provider.id)},
        )
        return {"status": "ignored", "reason": "credentials_incomplete"}

    provided_signature = request.headers.get("X-Twilio-Signature")
    if not provided_signature:
        raise HTTPException(status_code=403, detail="Missing signature")

    expected_signature = _compute_twilio_signature(
        auth_token=auth_token,
        url=str(request.url),
        params=[(key, value) for key, value in form_items],
    )

    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    existing = db.query(MessageEvent).filter(MessageEvent.provider_event_id == message_sid).first()
    if existing:
        return {"status": "ok", "processed": 0}

    contact_repository = ContactRepository(db)
    preference_resolver = ContactPreferenceResolver(db, provider.org_id)

    contact: Optional[Contact] = None
    contact_id = None
    if from_number:
        contact = contact_repository.find_by_sms(org_id=provider.org_id, phone_number=from_number)
        if contact:
            contact_id = contact.id

    preferences = None
    has_consent = True
    if from_number:
        preferences = preference_resolver.load(channel="sms", channel_address=from_number)
        if contact_id is None and preferences.contact_id is not None:
            contact_id = preferences.contact_id
        has_consent = preferences.is_channel_allowed("sms", from_number)
        if contact_id and not has_consent:
            has_consent = _has_active_consent(
                db=db,
                org_id=provider.org_id,
                contact_id=contact_id,
                channel="sms",
                incoming_address=from_number,
            )

    if from_number and (not has_consent or contact_id is None):
        if contact_id:
            opt_in_service = OptInRequestService(db)
            try:
                opt_in_service.enqueue_request(
                    org_id=provider.org_id,
                    contact_id=contact_id,
                    requested_channel="sms",
                    requested_address=from_number,
                    dispatch_immediately=False,
                )
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "Failed to enqueue opt-in request after denied SMS message",
                    extra={"provider_id": str(provider.id), "message_sid": message_sid},
                )
        logger.info(
            "Inbound SMS denied due to missing consent or contact",
            extra={"provider_id": str(provider.id), "message_sid": message_sid},
        )
        return {"status": "denied"}

    timestamp_provider = _parse_timestamp(
        payload_dict.get("Timestamp")
        or payload_dict.get("DateSent")
        or payload_dict.get("DateCreated")
    )

    sms_status = payload_dict.get("SmsStatus") or payload_dict.get("MessageStatus") or "received"

    masked_payload = _mask_payload(form_items)
    attributes = {
        "payload": masked_payload,
        "body_digest": None,
    }

    body = payload_dict.get("Body")
    if body:
        attributes["body_digest"] = hashlib.sha256(body.encode("utf-8")).hexdigest()

    event = MessageEvent(
        org_id=provider.org_id,
        connection_id=None,
        channel="sms",
        channel_address=from_number,
        contact_id=contact_id if has_consent else None,
        provider_event_id=message_sid,
        direction="inbound",
        timestamp_provider=timestamp_provider,
        delivery_status=sms_status,
        attributes=attributes,
    )

    db.add(event)
    db.commit()

    return {"status": "ok", "processed": 1}
