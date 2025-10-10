"""Email integrations webhook handlers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decrypt_credentials
from app.models.models import (
    ContactConsentAudit,
    MessageEvent,
    OptInStatusEnum,
    Provider,
    ProviderCredential,
)
from app.services.contacts.repository import ContactRepository

logger = logging.getLogger(__name__)

router = APIRouter()

MASK_TOKEN = "***redacted***"
BODY_MASK_KEYS = {"text", "html", "body"}
HEADER_MASK_KEYS = {"subject", "from", "from_email", "to", "cc", "bcc", "reply_to"}


def _normalize_email(value: Optional[str]) -> Optional[str]:
    return ContactRepository._normalize_email(value)


def _extract_email_address(value: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    if value:
        _, email = parseaddr(value)
        normalized = _normalize_email(email or value)
        if normalized:
            return normalized
    return _normalize_email(fallback)


def _normalize_subject(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_body(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _parse_timestamp(value: Optional[Any]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError):
            return datetime.now(timezone.utc)

    if isinstance(value, str):
        sanitized = value.strip()
        if not sanitized:
            return datetime.now(timezone.utc)

        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S%z",
        ):
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

    return datetime.now(timezone.utc)


def _mask_payload(value: Any) -> Any:
    if isinstance(value, dict):
        masked: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BODY_MASK_KEYS or lowered in HEADER_MASK_KEYS:
                masked[key] = MASK_TOKEN
            else:
                masked[key] = _mask_payload(item)
        return masked
    if isinstance(value, list):
        return [_mask_payload(item) for item in value]
    if isinstance(value, str):
        return value
    return value


def _compute_hmac_signature(*, secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _candidate_tokens(credentials: Dict[str, Any]) -> Iterable[str]:
    values: List[str] = []
    for key in ("inbound_verify_token", "inbound_secret", "webhook_token"):
        token = credentials.get(key)
        if isinstance(token, str):
            stripped = token.strip()
            if stripped:
                values.append(stripped)
        elif isinstance(token, (list, tuple, set)):
            for item in token:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        values.append(stripped)
    return values


def _find_provider_by_token(
    db: Session, token: Optional[str]
) -> Optional[Tuple[Provider, ProviderCredential, Dict[str, Any]]]:
    normalized = (token or "").strip()
    if not normalized:
        return None

    candidates = (
        db.query(Provider, ProviderCredential)
        .join(ProviderCredential, ProviderCredential.provider_id == Provider.id)
        .filter(ProviderCredential.is_active.is_(True))
        .filter(Provider.org_id == ProviderCredential.org_id)
        .filter(Provider.type.in_(["email", "sendgrid"]))
        .all()
    )

    for provider, credential in candidates:
        try:
            credentials = decrypt_credentials(credential.credentials_encrypted)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception(
                "Failed to decrypt credentials for provider",
                extra={"provider_id": str(provider.id)},
            )
            continue

        for candidate in _candidate_tokens(credentials):
            if hmac.compare_digest(candidate, normalized):
                return provider, credential, credentials

    return None


@router.get("/webhook")
def email_webhook_verify(
    *,
    token: str = Query(..., description="Token de verificação configurado no provedor."),
    challenge: str = Query(..., description="Valor de desafio enviado pelo provedor."),
    db: Session = Depends(get_db),
):
    provider_bundle = _find_provider_by_token(db, token)
    if not provider_bundle:
        raise HTTPException(status_code=403, detail="Verification failed")

    return PlainTextResponse(content=str(challenge))


def _ingest_email_event(
    *,
    db: Session,
    provider: Provider,
    payload: Dict[str, Any],
    request: Request,
    contact_repository: ContactRepository,
) -> bool:
    message_id = payload.get("message_id") or payload.get("event_id") or payload.get("sg_message_id")
    if not message_id:
        raise HTTPException(status_code=400, detail="Missing message identifier")

    existing = (
        db.query(MessageEvent)
        .filter(MessageEvent.provider_event_id == str(message_id))
        .first()
    )
    if existing:
        return False

    sender_email = _extract_email_address(
        payload.get("from"),
        fallback=payload.get("from_email") or payload.get("sender"),
    )
    if not sender_email:
        raise HTTPException(status_code=400, detail="Missing sender email")

    sender_name = None
    if payload.get("from"):
        sender_name = parseaddr(payload.get("from"))[0] or None
        if sender_name:
            sender_name = sender_name.strip() or None

    subject = _normalize_subject(payload.get("subject"))
    text_body = _normalize_body(payload.get("text") or payload.get("body"))
    html_body = _normalize_body(payload.get("html"))
    timestamp = _parse_timestamp(payload.get("timestamp") or payload.get("date"))

    contact = contact_repository.find_by_email(org_id=provider.org_id, email=sender_email)
    if not contact:
        contact_payload: Dict[str, Any] = {
            "org_id": provider.org_id,
            "email": sender_email,
            "source": "email_webhook",
            "source_metadata": {
                "provider": provider.name,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        if sender_name:
            contact_payload["full_name"] = sender_name
        contact = contact_repository.create_contact(**contact_payload)

    attributes: Dict[str, Any] = {
        "payload": _mask_payload(payload),
    }
    if subject:
        attributes["subject_digest"] = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    if text_body:
        attributes["text_digest"] = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    if html_body:
        attributes["html_digest"] = hashlib.sha256(html_body.encode("utf-8")).hexdigest()
        attributes["has_html"] = True

    delivery_status = payload.get("event") or "received"

    event = MessageEvent(
        org_id=provider.org_id,
        provider_event_id=str(message_id),
        direction="inbound",
        channel="email",
        channel_address=sender_email,
        contact_id=getattr(contact, "id", None),
        timestamp_provider=timestamp,
        delivery_status=delivery_status,
        attributes=attributes,
    )

    db.add(event)

    proof_hash = hashlib.sha256(
        f"email:{provider.org_id}:{contact.id}:{message_id}".encode("utf-8")
    ).hexdigest()
    existing_audit = (
        db.query(ContactConsentAudit)
        .filter(ContactConsentAudit.org_id == provider.org_id)
        .filter(ContactConsentAudit.contact_id == contact.id)
        .filter(ContactConsentAudit.proof_hash == proof_hash)
        .first()
    )
    if not existing_audit:
        audit_entry = ContactConsentAudit(
            org_id=provider.org_id,
            contact_id=contact.id,
            opt_in_id=None,
            channel="email",
            channel_address=sender_email,
            status=OptInStatusEnum.granted,
            source="webhook",
            agent="email_webhook",
            request_ip=getattr(request.client, "host", None),
            proof_hash=proof_hash,
            context={
                "provider_event_id": str(message_id),
                "provider": provider.name,
                "masked_subject": MASK_TOKEN if subject else None,
            },
        )
        db.add(audit_entry)

    return True


@router.post("/webhook")
async def email_webhook_receive(
    request: Request,
    *,
    token: str = Query(..., description="Token configurado para autenticar requisições inbound."),
    db: Session = Depends(get_db),
):
    provider_bundle = _find_provider_by_token(db, token)
    if not provider_bundle:
        raise HTTPException(status_code=403, detail="Unknown provider token")

    provider, _credential, credentials = provider_bundle

    raw_body = await request.body()

    signing_secret = credentials.get("inbound_signing_secret") or credentials.get("signing_secret")
    if signing_secret:
        provided_signature = request.headers.get("X-Email-Signature")
        if not provided_signature:
            raise HTTPException(status_code=403, detail="Missing signature header")
        expected_signature = _compute_hmac_signature(secret=signing_secret, payload=raw_body)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        decoded = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    events: List[Dict[str, Any]]
    if isinstance(decoded, list):
        events = [item for item in decoded if isinstance(item, dict)]
    elif isinstance(decoded, dict):
        events = [decoded]
    else:
        raise HTTPException(status_code=400, detail="Unsupported payload structure")

    if not events:
        return {"status": "ignored", "processed": 0}

    contact_repository = ContactRepository(db)
    processed = 0

    for entry in events:
        processed_event = _ingest_email_event(
            db=db,
            provider=provider,
            payload=entry,
            request=request,
            contact_repository=contact_repository,
        )
        if processed_event:
            processed += 1

    if processed:
        db.commit()
        status = "ok"
    else:
        status = "ignored"

    return {"status": status, "processed": processed}
