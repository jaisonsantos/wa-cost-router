import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Iterable, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decrypt_credentials
from app.core.circuit_breaker import (
    CircuitBreakerStore,
    CircuitState,
    get_circuit_breaker_store,
)
from app.core.rate_limiter import (
    RateLimitExceeded,
    RateLimitStatus,
    RateLimiter,
    get_rate_limiter,
)
from app.models.models import (
    MessageJob,
    DeliveryAttempt,
    CostRecord,
    Provider,
    ProviderCredential,
    MessageEvent,
    RateCard,
    JobStatusEnum,
    AttemptStatusEnum,
    Contact,
    ContactChannelOptIn,
    OptInStatusEnum,
)
from app.core.normalization import (
    normalize_country_code,
    normalize_international_phone,
    strip_to_none,
)
from app.services.contacts import OptInRequestService
from app.services.provider_connectors import get_connector
from app.services.routing import ContactOptOutError
from app.services.routing_engine import RoutingEngine
from prometheus_client import Counter, Gauge

router = APIRouter()
logger = logging.getLogger(__name__)

MESSAGES_SEND_COUNTER = Counter(
    "messages_send_total",
    "Total de requisições /messages/send processadas",
    labelnames=["status", "provider"],
)

DELIVERY_ATTEMPTS_COUNTER = Counter(
    "messages_delivery_attempts_total",
    "Total de tentativas de entrega por provedor",
    labelnames=["provider_id", "provider", "outcome"],
)

CIRCUIT_STATE_GAUGE = Gauge(
    "messages_circuit_breaker_state",
    "Estado atual do circuito por provedor (0=closed,1=half-open,2=open)",
    labelnames=["provider_id"],
)


PHONE_CHANNELS = {"whatsapp", "sms"}


@dataclass
class SendMessageContext:
    current_user: dict
    rate_status: RateLimitStatus


def _limit_messages_send(
    response: Response,
    current_user: dict = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> SendMessageContext:
    scope = "messages_send"
    identifier = str(current_user["org_id"])
    try:
        status = limiter.hit(
            scope,
            identifier,
            limit=settings.RATE_LIMIT_MESSAGES_PER_MIN,
            ttl_seconds=60,
        )
    except RateLimitExceeded as exc:
        logger.warning(
            "Rate limit exceeded for message send",
            extra={
                "event": "rate_limit_exceeded",
                "scope": scope,
                "org_id": identifier,
                "retry_after": exc.retry_after,
                "limit": exc.limit,
            },
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for message sending",
            headers={
                "Retry-After": str(exc.retry_after),
                "X-RateLimit-Remaining": "0",
            },
        ) from exc

    response.headers["X-RateLimit-Remaining"] = str(status.remaining)
    return SendMessageContext(current_user=current_user, rate_status=status)

class SendMessageRequest(BaseModel):
    idempotency_key: str
    channel: str
    template_id: str
    template_category: str = "marketing"
    variables: Dict[str, Any] = {}
    contact_id: Optional[UUID] = None
    channel_address: Optional[str] = None
    country_iso: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_payload(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "channel_address" not in values:
                legacy = values.get("to_number")
                if legacy is not None:
                    values["channel_address"] = legacy

            channel_value = values.get("channel")
            if strip_to_none(channel_value) is None:
                if values.get("channel_address") is not None or values.get("to_number") is not None:
                    values["channel"] = "whatsapp"
        return values

    @field_validator("idempotency_key", "template_id", "template_category", mode="before")
    @classmethod
    def _trim_required_strings(cls, value: Any) -> Any:
        return strip_to_none(value)

    @field_validator("channel", mode="before")
    @classmethod
    def _normalize_channel(cls, value: Any) -> str:
        normalized = strip_to_none(value)
        if normalized is None:
            raise ValueError("channel is required")
        return normalized.lower()

    @field_validator("channel_address", mode="before")
    @classmethod
    def _normalize_channel_address(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = strip_to_none(value)
        return normalized

    @field_validator("country_iso", mode="before")
    @classmethod
    def _normalize_country(cls, value: Any) -> Any:
        return normalize_country_code(value)

    @model_validator(mode="after")
    def _validate_recipient(self) -> "SendMessageRequest":
        if self.contact_id is None and self.channel_address is None:
            raise ValueError("Either contact_id or channel_address must be provided")

        if self.channel_address is not None:
            normalized = _normalize_channel_address_value(self.channel, self.channel_address)
            if normalized is None:
                raise ValueError("Invalid channel_address for the requested channel")
            self.channel_address = normalized

        return self

class SendMessageResponse(BaseModel):
    job_id: str
    status: str
    provider_used: Optional[str] = None
    estimated_cost: Optional[int] = None
    message: str

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    data: SendMessageRequest,
    context: SendMessageContext = Depends(_limit_messages_send),
    db: Session = Depends(get_db),
):
    """
    Envia mensagem via roteamento inteligente
    - Aplica regras
    - Escolhe provedor
    - Tenta com retry e fallback
    - Registra custo e tentativas
    """
    
    # 1. Verificar idempotência
    current_user = context.current_user

    existing_job = db.query(MessageJob).filter(
        MessageJob.org_id == current_user["org_id"],
        MessageJob.idempotency_key == data.idempotency_key
    ).first()
    
    if existing_job:
        return SendMessageResponse(
            job_id=str(existing_job.id),
            status=existing_job.status.value,
            message="Message already processed (idempotent)"
        )
    
    # 2. Resolver endereço do canal/contato
    resolved_contact_id, resolved_address = _resolve_recipient_context(
        db=db,
        org_id=current_user["org_id"],
        channel=data.channel,
        contact_id=data.contact_id,
        provided_address=data.channel_address,
    )

    if resolved_address is None:
        raise HTTPException(status_code=422, detail="Unable to resolve channel address")

    data.channel_address = resolved_address
    if resolved_contact_id is not None:
        data.contact_id = resolved_contact_id

    # 3. Inferir país do endereço se não fornecido
    if data.channel in PHONE_CHANNELS:
        country_iso = data.country_iso or _infer_country_from_number(resolved_address)
    else:
        country_iso = data.country_iso or "XX"

    # 4. Criar job
    job_identifier = uuid.uuid4()
    job = MessageJob(
        id=job_identifier,
        org_id=current_user["org_id"],
        idempotency_key=data.idempotency_key,
        to_number=resolved_address,
        channel=data.channel,
        channel_address=resolved_address,
        contact_id=resolved_contact_id,
        template_id=data.template_id,
        template_category=data.template_category,
        variables=data.variables,
        country_iso=country_iso,
        status=JobStatusEnum.processing
    )
    db.add(job)

    try:
        _commit_or_raise(db)
    except Exception as exc:  # pragma: no cover - committed failure handled below
        logger.exception(
            "Failed to persist message job %s for org %s: %s",
            str(job_identifier),
            current_user["org_id"],
            exc,
        )
        try:
            existing_job = db.query(MessageJob).filter(
                MessageJob.org_id == current_user["org_id"],
                MessageJob.idempotency_key == data.idempotency_key,
            ).first()
        except Exception:  # pragma: no cover - defensive fallback
            existing_job = None

        if existing_job:
            return SendMessageResponse(
                job_id=str(existing_job.id),
                status=existing_job.status.value,
                provider_used=None,
                estimated_cost=None,
                message="Message already processed (idempotent)",
            )

        return SendMessageResponse(
            job_id=str(job_identifier),
            status=JobStatusEnum.failed_final.value,
            provider_used=None,
            estimated_cost=None,
            message="Message job persistence error",
        )

    # 4. Escolher provedor via motor de decisão
    circuit_breaker = get_circuit_breaker_store()
    engine = RoutingEngine(db, current_user["org_id"], circuit_breaker=circuit_breaker)
    try:
        routing_decision = engine.select_provider(
            country_iso=country_iso,
            category=data.template_category,
            template_id=data.template_id,
            contact_address=resolved_address,
        )
    except ContactOptOutError as exc:
        job.status = JobStatusEnum.failed_final
        try:
            _commit_or_raise(db)
        except Exception:
            logger.exception(
                "Failed to persist consent violation for job %s in org %s",
                job_identifier,
                current_user["org_id"],
            )
        else:
            try:
                if exc.contact_id:
                    opt_in_service = OptInRequestService(db)
                    opt_in_service.enqueue_request(
                        org_id=current_user["org_id"],
                        contact_id=exc.contact_id,
                        requested_channel=exc.channel or job.channel,
                        requested_address=exc.channel_address or job.channel_address,
                        trigger_metadata={
                            "message_job_id": str(job_identifier),
                            "template_id": data.template_id,
                            "template_category": data.template_category,
                        },
                    )
            except Exception:
                logger.exception(
                    "Failed to enqueue opt-in solicitation after consent violation",
                    extra={
                        "org_id": str(current_user["org_id"]),
                        "contact_id": str(exc.contact_id) if exc.contact_id else None,
                    },
                )
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Routing engine failure for job %s in org %s: %s",
            job_identifier,
            current_user["org_id"],
            exc,
        )
        status_value = JobStatusEnum.failed_final.value
        try:  # pragma: no cover - best effort persistence
            job_to_update = _ensure_job_attached(db, job)
            if job_to_update is not None:
                job_to_update.status = JobStatusEnum.failed_final
                status_value = job_to_update.status.value
        except Exception:
            logger.exception("Unable to mark job %s as failed after routing error", job_identifier)
        return SendMessageResponse(
            job_id=str(job_identifier),
            status=status_value,
            provider_used=None,
            estimated_cost=None,
            message="Routing engine error",
        )
    
    if not routing_decision:
        job.status = JobStatusEnum.failed_final
        try:
            _commit_or_raise(db)
        except Exception:
            logger.exception("Failed to mark job %s as failed after empty routing decision", job_identifier)
        raise HTTPException(status_code=400, detail="No provider available for this route")
    
    # 5. Tentar envio com fallback
    estimated_cost_minor = _normalize_estimated_cost(
        routing_decision.get("estimated_cost")
    )

    baseline_cost_minor = engine.calculate_baseline_cost(
        country_iso=country_iso,
        category=data.template_category,
    )

    try:
        result = await _attempt_delivery_with_fallback(
            db=db,
            job=job,
            routing_decision=routing_decision,
            data=data,
            org_id=current_user["org_id"],
            estimated_cost_minor=estimated_cost_minor,
            baseline_cost_minor=baseline_cost_minor,
            circuit_breaker=circuit_breaker,
            job_identifier=job_identifier,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Unexpected delivery failure for job %s via provider %s: %s",
            job_identifier,
            routing_decision.get("provider_id") if routing_decision else None,
            exc,
        )
        status_value = JobStatusEnum.failed_final.value
        try:  # pragma: no cover - best effort persistence
            job_to_update = _ensure_job_attached(db, job)
            if job_to_update is not None:
                job_to_update.status = JobStatusEnum.failed_final
                status_value = job_to_update.status.value
        except Exception:
            logger.exception("Unable to mark job %s as failed after delivery error", job_identifier)
        result = {
            "status": status_value,
            "provider_name": None,
            "message": "Delivery orchestration error",
        }
    
    final_provider = result.get("provider_name") or "none"
    try:
        MESSAGES_SEND_COUNTER.labels(status=result["status"], provider=final_provider).inc()
    except Exception:  # pragma: no cover - metrics failures must not break API
        logger.exception(
            "Failed to record messages_send_total metric",
            extra={
                "event": "metrics_error",
                "metric": "messages_send_total",
                "provider": final_provider,
            },
        )

    return SendMessageResponse(
        job_id=str(job_identifier),
        status=result["status"],
        provider_used=result.get("provider_name"),
        estimated_cost=estimated_cost_minor,
        message=result.get("message", "Message sent successfully")
    )

async def _attempt_delivery_with_fallback(
    db: Session,
    job: MessageJob,
    routing_decision: Dict[str, Any],
    data: SendMessageRequest,
    org_id: str,
    estimated_cost_minor: int,
    baseline_cost_minor: int,
    circuit_breaker: CircuitBreakerStore,
    job_identifier: UUID,
) -> Dict[str, Any]:
    """Tenta entrega com retry e fallback"""

    org_uuid = _coerce_uuid(org_id)
    if org_uuid is None:
        logger.error("Invalid organization identifier %r for job %s", org_id, job_identifier)
        job.status = JobStatusEnum.failed_final
        try:
            _commit_or_raise(db)
        except Exception:
            logger.exception("Failed to persist invalid organization failure for job %s", job_identifier)
        return {
            "status": job.status.value,
            "message": "Invalid organization context",
        }

    raw_providers = []

    primary_identifier = routing_decision.get("provider_id")
    if primary_identifier is not None:
        raw_providers.append(primary_identifier)

    fallback_chain = routing_decision.get("fallback_chain")
    if fallback_chain in (None, ""):
        fallback_candidates: Iterable[Any] = []
    elif isinstance(fallback_chain, Iterable) and not isinstance(fallback_chain, (str, bytes)):
        fallback_candidates = fallback_chain
    else:
        logger.warning(
            "Invalid fallback chain %r for job %s; ignoring",
            fallback_chain,
            job_identifier,
        )
        fallback_candidates = []

    raw_providers.extend(list(fallback_candidates))

    providers_to_try = []
    for raw_identifier in raw_providers:
        provider_uuid = _coerce_uuid(raw_identifier)
        if provider_uuid is None:
            logger.warning("Skipping invalid provider identifier %r", raw_identifier)
            continue
        providers_to_try.append(provider_uuid)

    attempt_number = 0

    for provider_id in providers_to_try:
        attempt_number += 1

        provider = db.query(Provider).filter(
            Provider.id == provider_id,
            Provider.org_id == org_uuid,
        ).first()
        if not provider:
            logger.warning("Provider %s not found for org %s", provider_id, org_uuid)
            continue

        state = circuit_breaker.get_state(str(provider.id))
        _record_circuit_state(provider.id, state)
        if state.is_blocked():
            logger.info(
                "Skipping provider %s on attempt %s due to circuit state %s",
                provider.id,
                attempt_number,
                state.state,
                extra={
                    "event": "circuit_breaker_skip",
                    "provider_id": str(provider.id),
                    "provider_name": provider.name,
                    "state": state.state,
                    "failure_count": state.failure_count,
                },
            )
            DELIVERY_ATTEMPTS_COUNTER.labels(
                provider_id=str(provider.id),
                provider=provider.name,
                outcome="skipped_circuit",
            ).inc()
            continue

        credential = db.query(ProviderCredential).filter(
            ProviderCredential.org_id == org_uuid,
            ProviderCredential.provider_id == provider_id,
            ProviderCredential.is_active.is_(True)
        ).first()

        if not credential:
            logger.warning(f"No credentials for provider {provider_id}")
            continue

        try:
            credentials_payload = decrypt_credentials(credential.credentials_encrypted)
        except Exception as exc:
            logger.error(f"Invalid credentials payload for provider {provider_id}: {exc}")
            continue

        for retry in range(3):
            connector = get_connector(
                provider.name,
                credentials_payload,
                provider.base_url
            )

            try:
                result = await connector.send_message(
                    to_number=job.channel_address,
                    template_id=data.template_id,
                    variables=data.variables
                )
            except Exception as exc:
                logger.error(f"Delivery error: {str(exc)}")
                attempt = DeliveryAttempt(
                    message_job_id=job_identifier,
                    provider_id=provider.id,
                    attempt_number=attempt_number,
                    status=AttemptStatusEnum.failed,
                    error_code="EXCEPTION",
                    error_message=str(exc)
                )
                db.add(attempt)
                try:
                    _commit_or_raise(db)
                except Exception:
                    logger.exception("Failed to record delivery exception for provider %s", provider.id)
                    raise

                new_state = circuit_breaker.mark_failure(str(provider.id))
                _record_circuit_state(provider.id, new_state)
                _log_circuit_transition(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    state=new_state,
                    reason="exception",
                )
                DELIVERY_ATTEMPTS_COUNTER.labels(
                    provider_id=str(provider.id),
                    provider=provider.name,
                    outcome="exception",
                ).inc()
                break

            attempt = DeliveryAttempt(
                message_job_id=job_identifier,
                provider_id=provider.id,
                attempt_number=attempt_number,
                status=AttemptStatusEnum.success if result["success"] else AttemptStatusEnum.failed,
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
                latency_ms=result.get("latency_ms"),
                provider_message_id=result.get("provider_message_id"),
                provider_response=result.get("response")
            )
            db.add(attempt)

            if result["success"]:
                new_state = circuit_breaker.mark_success(str(provider.id))
                _record_circuit_state(provider.id, new_state)
                _log_circuit_transition(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    state=new_state,
                    reason="success",
                )

                unit_cost_minor, currency = _resolve_pricing_context(
                    db=db,
                    provider_id=provider.id,
                    country_iso=job.country_iso,
                    category=job.template_category,
                    fallback_cost=estimated_cost_minor,
                )

                cost_record = CostRecord(
                    message_job_id=job_identifier,
                    provider_id=provider.id,
                    price_eur=unit_cost_minor,
                    country_iso=job.country_iso,
                    category=job.template_category,
                    price_table_version="v1",
                )
                db.add(cost_record)

                provider_message_id = result.get("provider_message_id")
                if not provider_message_id:
                    provider_message_id = f"job-{job_identifier}-attempt-{attempt_number}"

                message_event = MessageEvent(
                    org_id=job.org_id,
                    message_job_id=job_identifier,
                    connection_id=None,
                    channel=job.channel,
                    channel_address=job.channel_address,
                    contact_id=job.contact_id,
                    provider_event_id=provider_message_id,
                    direction="outbound",
                    template_name=job.template_id,
                    category=job.template_category,
                    country_iso=job.country_iso,
                    phone_cc=None,
                    timestamp_provider=datetime.now(timezone.utc),
                    delivery_status="delivered",
                    unit_cost_minor=unit_cost_minor,
                    baseline_cost_minor=baseline_cost_minor,
                    currency=currency,
                )
                db.add(message_event)

                job.status = (
                    JobStatusEnum.delivered
                    if attempt_number == 1
                    else JobStatusEnum.delivered_with_fallback
                )
                _commit_or_raise(db)

                DELIVERY_ATTEMPTS_COUNTER.labels(
                    provider_id=str(provider.id),
                    provider=provider.name,
                    outcome="success",
                ).inc()

                return {
                    "status": job.status.value,
                    "provider_name": provider.name,
                    "message": "Message delivered successfully"
                }

            if result.get("error_code") in ["429", "timeout"]:
                await asyncio.sleep(2 ** retry)
                continue

            new_state = circuit_breaker.mark_failure(str(provider.id))
            _record_circuit_state(provider.id, new_state)
            _log_circuit_transition(
                provider_id=provider.id,
                provider_name=provider.name,
                state=new_state,
                reason="failure",
            )
            DELIVERY_ATTEMPTS_COUNTER.labels(
                provider_id=str(provider.id),
                provider=provider.name,
                outcome="failure",
            ).inc()

            break

    # Todos os providers falharam
    job.status = JobStatusEnum.failed_final
    _commit_or_raise(db)

    return {
        "status": job.status.value,
        "message": "All providers failed"
    }


def _record_circuit_state(provider_id: UUID | str, state: CircuitState) -> None:
    try:
        value_map = {"closed": 0, "half-open": 1, "open": 2}
        CIRCUIT_STATE_GAUGE.labels(provider_id=str(provider_id)).set(value_map.get(state.state, 0))
    except Exception:  # pragma: no cover - metrics failures must not break API
        logger.exception(
            "Failed to record circuit state metric",
            extra={"event": "metrics_error", "metric": "messages_circuit_breaker_state"},
        )


def _log_circuit_transition(
    *,
    provider_id: UUID | str,
    provider_name: str,
    state: CircuitState,
    reason: str,
) -> None:
    payload = {
        "event": "circuit_breaker_state",
        "provider_id": str(provider_id),
        "provider_name": provider_name,
        "state": state.state,
        "failure_count": state.failure_count,
        "reason": reason,
    }

    if state.state == "open":
        logger.warning(
            "Circuit breaker opened for provider %s (%s) after %s",
            provider_name,
            provider_id,
            reason,
            extra=payload,
        )
    elif state.state == "half-open":
        logger.info(
            "Circuit breaker half-open for provider %s (%s)",
            provider_name,
            provider_id,
            extra=payload,
        )
    elif state.state == "closed" and reason == "success":
        logger.info(
            "Circuit breaker closed for provider %s (%s)",
            provider_name,
            provider_id,
            extra=payload,
        )


def _normalize_channel_address_value(
    channel: Optional[str],
    address: Optional[str],
) -> Optional[str]:
    trimmed = strip_to_none(address)
    if trimmed is None:
        return None

    normalized_channel = strip_to_none(channel)
    if normalized_channel:
        normalized_channel = normalized_channel.lower()

    if normalized_channel in PHONE_CHANNELS:
        return normalize_international_phone(trimmed)

    return trimmed


def _select_contact_channel_address(
    *,
    db: Session,
    contact: Contact,
    channel: Optional[str],
) -> Optional[str]:
    normalized_channel = strip_to_none(channel)
    if normalized_channel:
        normalized_channel = normalized_channel.lower()

    if not normalized_channel:
        return None

    opt_in = (
        db.query(ContactChannelOptIn)
        .filter(ContactChannelOptIn.org_id == contact.org_id)
        .filter(ContactChannelOptIn.contact_id == contact.id)
        .filter(ContactChannelOptIn.channel == normalized_channel)
        .filter(ContactChannelOptIn.status == OptInStatusEnum.granted)
        .order_by(
            ContactChannelOptIn.version.desc(),
            ContactChannelOptIn.updated_at.desc(),
        )
        .first()
    )

    if opt_in and opt_in.channel_address:
        normalized = _normalize_channel_address_value(normalized_channel, opt_in.channel_address)
        if normalized is not None:
            return normalized

    if normalized_channel in PHONE_CHANNELS and contact.phone:
        normalized = _normalize_channel_address_value(normalized_channel, contact.phone)
        if normalized is not None:
            return normalized

    if normalized_channel == "email" and contact.email:
        return contact.email.strip()

    return None


def _resolve_recipient_context(
    *,
    db: Session,
    org_id: Any,
    channel: str,
    contact_id: Optional[UUID],
    provided_address: Optional[str],
) -> Tuple[Optional[UUID], Optional[str]]:
    org_uuid = _coerce_uuid(org_id)
    if org_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid organization context")

    normalized_channel = strip_to_none(channel)
    if normalized_channel:
        normalized_channel = normalized_channel.lower()

    resolved_contact_id: Optional[UUID] = None
    resolved_address = provided_address

    if contact_id is not None:
        contact = (
            db.query(Contact)
            .filter(Contact.id == contact_id)
            .filter(Contact.org_id == org_uuid)
            .first()
        )

        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        resolved_contact_id = contact.id

        if resolved_address is not None:
            normalized_address = _normalize_channel_address_value(normalized_channel, resolved_address)
            if normalized_address is None:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid channel_address for the requested channel",
                )
            resolved_address = normalized_address
        else:
            resolved_address = _select_contact_channel_address(
                db=db,
                contact=contact,
                channel=normalized_channel,
            )
            if resolved_address is None:
                raise HTTPException(
                    status_code=422,
                    detail="Contact has no address for requested channel",
                )
    else:
        if resolved_address is None:
            raise HTTPException(
                status_code=422,
                detail="channel_address is required when contact_id is not provided",
            )

        normalized_address = _normalize_channel_address_value(normalized_channel, resolved_address)
        if normalized_address is None:
            raise HTTPException(
                status_code=422,
                detail="Invalid channel_address for the requested channel",
            )
        resolved_address = normalized_address

    return resolved_contact_id, resolved_address


def _normalize_estimated_cost(value: Any) -> int:
    """Coerce arbitrary estimated cost values into a non-negative integer."""

    if value is None:
        return 0

    try:
        cost = int(value)
    except (TypeError, ValueError):
        logger.warning("Invalid estimated cost %r; defaulting to 0", value)
        return 0

    return max(cost, 0)


def _infer_country_from_number(number: str) -> str:
    """Inferir país do código do número (simplificado)"""
    country_codes = {
        "+1": "US",
        "+44": "GB",
        "+55": "BR",
        "+351": "PT",
        "+34": "ES",
        "+49": "DE",
        "+33": "FR"
    }

    for code, country in country_codes.items():
        if number.startswith(code):
            return country

    return "XX"  # Unknown


def _coerce_uuid(value: Any) -> Optional[UUID]:
    """Safely convert arbitrary identifiers into UUID objects."""

    if isinstance(value, UUID):
        return value

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _commit_or_raise(db: Session) -> None:
    """Commit the current transaction or propagate the failure after rollback."""

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise exc
    except Exception:
        db.rollback()
        raise


def _ensure_job_attached(db: Session, job: MessageJob) -> MessageJob:
    """Reload the job from the database if the session was reset."""

    if job is None or getattr(job, "id", None) is None:
        return job

    refreshed = db.get(MessageJob, job.id)
    return refreshed or job


def _resolve_pricing_context(
    *,
    db: Session,
    provider_id: UUID,
    country_iso: Optional[str],
    category: Optional[str],
    fallback_cost: int,
) -> Tuple[int, Optional[str]]:
    """Resolve unit cost and currency for a delivery attempt."""

    if category is None:
        return fallback_cost, None

    rate = (
        db.query(RateCard)
        .filter(
            RateCard.provider_id == provider_id,
            RateCard.country_iso == country_iso,
            RateCard.category == category,
        )
        .order_by(RateCard.effective_from.desc())
        .first()
    )

    if not rate and country_iso != "GLOBAL":
        rate = (
            db.query(RateCard)
            .filter(
                RateCard.provider_id == provider_id,
                RateCard.country_iso == "GLOBAL",
                RateCard.category == category,
            )
            .order_by(RateCard.effective_from.desc())
            .first()
        )

    if rate:
        return rate.unit_cost_minor, rate.currency

    return fallback_cost, None

@router.get("/jobs")
def list_message_jobs(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista jobs de mensagens da organização"""
    query = db.query(MessageJob).filter(
        MessageJob.org_id == current_user["org_id"]
    )
    
    if status:
        try:
            status_enum = JobStatusEnum(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(MessageJob.status == status_enum)

    jobs = query.order_by(MessageJob.created_at.desc()).limit(100).all()

    job_ids = [job.id for job in jobs]
    cost_map: Dict[str, int] = {}
    if job_ids:
        cost_rows = (
            db.query(CostRecord.message_job_id, func.sum(CostRecord.price_eur))
            .filter(CostRecord.message_job_id.in_(job_ids))
            .group_by(CostRecord.message_job_id)
            .all()
        )
        cost_map = {str(job_id): total or 0 for job_id, total in cost_rows}

    return [
        {
            "id": str(job.id),
            "status": job.status.value,
            "to_number": job.to_number,
            "channel": job.channel,
            "channel_address": job.channel_address,
            "contact_id": str(job.contact_id) if job.contact_id else None,
            "template_id": job.template_id,
            "template_category": job.template_category,
            "country_iso": job.country_iso,
            "created_at": job.created_at.isoformat(),
            "total_cost_minor": cost_map.get(str(job.id)),
        }
        for job in jobs
    ]

@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Consulta status de um job"""
    job = db.query(MessageJob).filter(
        MessageJob.id == job_id,
        MessageJob.org_id == current_user["org_id"]
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    attempts = (
        db.query(DeliveryAttempt, Provider)
        .join(Provider, DeliveryAttempt.provider_id == Provider.id)
        .filter(DeliveryAttempt.message_job_id == job.id)
        .order_by(DeliveryAttempt.attempt_number.asc())
        .all()
    )

    total_cost = (
        db.query(func.sum(CostRecord.price_eur))
        .filter(CostRecord.message_job_id == job.id)
        .scalar()
    )

    return {
        "id": str(job.id),
        "status": job.status.value,
        "to_number": job.to_number,
        "channel": job.channel,
        "channel_address": job.channel_address,
        "contact_id": str(job.contact_id) if job.contact_id else None,
        "template_id": job.template_id,
        "template_category": job.template_category,
        "country_iso": job.country_iso,
        "created_at": job.created_at.isoformat(),
        "total_cost_minor": total_cost or 0,
        "attempts": [
            {
                "id": str(a.id),
                "attempt_number": a.attempt_number,
                "status": a.status.value,
                "provider_id": str(a.provider_id),
                "provider_name": provider.name,
                "latency_ms": a.latency_ms,
                "error_code": a.error_code,
                "error_message": a.error_message,
            }
            for a, provider in attempts
        ],
    }
