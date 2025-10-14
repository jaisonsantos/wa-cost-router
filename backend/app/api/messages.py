import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.circuit_breaker import get_circuit_breaker_store
from app.core.rate_limiter import (
    RateLimitExceeded,
    RateLimitStatus,
    RateLimiter,
    get_rate_limiter,
)
from app.models.models import (
    MessageJob,
    CostRecord,
    RoutedAction,
    JobStatusEnum,
    Contact,
    ContactChannelOptIn,
    OptInStatusEnum,
    DeliveryAttempt,
    Provider,
)
from app.core.normalization import (
    normalize_country_code,
    normalize_international_phone,
    strip_to_none,
)
from app.core.pii import (
    mask_contact_point,
    sanitize_template_variables,
)
from app.services.contacts import OptInRequestService
from app.services.routing import ContactOptOutError, RoutingPolicyViolation
from app.services.routing_engine import RoutingEngine
from app.services.messages.delivery import (
    DeliveryContext,
    DryRunNoRouteAvailable,
    MessageDeliveryDryRunService,
    commit_or_raise,
    coerce_uuid,
)
from app.workers import message_send as message_worker

router = APIRouter()
logger = logging.getLogger(__name__)

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


class RoutedActionItem(BaseModel):
    id: UUID
    rule_id: Optional[UUID]
    rule_name: Optional[str]
    status: str
    provider_id: Optional[UUID]
    provider_name: Optional[str]
    attempt_number: Optional[int]
    cost_minor: Optional[int]
    connector_response: Optional[Dict[str, Any]]
    created_at: datetime
    message_event_id: Optional[UUID]
    dry_run: bool = False
    estimated_cost_minor: Optional[int] = None
    baseline_cost_minor: Optional[int] = None
    fallback_chain: list[Dict[str, Optional[str]]] = Field(default_factory=list)


class RoutedActionChainResponse(BaseModel):
    job_id: UUID
    actions: list[RoutedActionItem]
    latest_simulation: Optional["DryRunSimulationSummary"] = None


class DryRunSimulationSummary(BaseModel):
    rule_id: Optional[UUID]
    rule_name: Optional[str]
    provider_id: Optional[UUID]
    provider_name: Optional[str]
    estimated_cost_minor: int
    baseline_cost_minor: int
    fallback_chain: list[Dict[str, Optional[str]]] = Field(default_factory=list)


def _serialize_routed_action(
    *, job_id: UUID, action: RoutedAction
) -> Tuple[Optional[RoutedActionItem], Optional[Dict[str, Any]]]:
    payload = action.provider_response or {}
    if payload.get("job_id") != str(job_id):
        return None, None

    fallback_chain = _normalize_fallback_chain_payload(payload.get("fallback_chain"))
    estimated_cost = _coerce_int(payload.get("estimated_cost_minor"))
    baseline_cost = _coerce_int(payload.get("baseline_cost_minor"))

    item = RoutedActionItem(
        id=action.id,
        rule_id=action.rule_id,
        rule_name=payload.get("rule_name"),
        status=action.status,
        provider_id=coerce_uuid(payload.get("provider_id")),
        provider_name=payload.get("provider_name"),
        attempt_number=payload.get("attempt_number"),
        cost_minor=action.cost_minor,
        connector_response=payload.get("connector_response"),
        created_at=action.created_at,
        message_event_id=action.message_event_id,
        dry_run=bool(action.dry_run),
        estimated_cost_minor=estimated_cost,
        baseline_cost_minor=baseline_cost,
        fallback_chain=fallback_chain,
    )
    return item, payload


def _normalize_fallback_chain_payload(
    value: Any,
) -> list[Dict[str, Optional[str]]]:
    if not value:
        return []

    normalized: list[Dict[str, Optional[str]]] = []
    if isinstance(value, list):
        for candidate in value:
            if not isinstance(candidate, dict):
                continue
            normalized.append(
                {
                    "provider_id": str(candidate.get("provider_id"))
                    if candidate.get("provider_id") is not None
                    else None,
                    "provider_name": (
                        str(candidate.get("provider_name"))
                        if candidate.get("provider_name") is not None
                        else None
                    ),
                }
            )
    return normalized


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return None


def _build_dry_run_summary_from_payload(
    payload: Dict[str, Any]
) -> Optional[DryRunSimulationSummary]:
    if not payload:
        return None

    estimated_cost = _coerce_int(payload.get("estimated_cost_minor"))
    baseline_cost = _coerce_int(payload.get("baseline_cost_minor"))
    if estimated_cost is None or baseline_cost is None:
        return None

    fallback_chain = _normalize_fallback_chain_payload(payload.get("fallback_chain"))
    return DryRunSimulationSummary(
        rule_id=coerce_uuid(payload.get("rule_id")),
        rule_name=payload.get("rule_name"),
        provider_id=coerce_uuid(payload.get("provider_id")),
        provider_name=payload.get("provider_name"),
        estimated_cost_minor=estimated_cost,
        baseline_cost_minor=baseline_cost,
        fallback_chain=fallback_chain,
    )


def _build_routing_chain_response(
    *,
    job_id: UUID,
    actions: list[RoutedAction],
    simulation_payload: Optional[Dict[str, Any]] = None,
) -> RoutedActionChainResponse:
    serialized: list[RoutedActionItem] = []
    latest_simulation = simulation_payload

    for action in actions:
        item, payload = _serialize_routed_action(job_id=job_id, action=action)
        if item is None:
            continue
        serialized.append(item)
        if latest_simulation is None and action.dry_run and payload is not None:
            latest_simulation = payload

    summary = (
        _build_dry_run_summary_from_payload(latest_simulation)
        if latest_simulation
        else None
    )

    return RoutedActionChainResponse(
        job_id=job_id,
        actions=serialized,
        latest_simulation=summary,
    )


def _load_routed_actions(db: Session, job: MessageJob) -> list[RoutedAction]:
    return (
        db.query(RoutedAction)
        .filter(RoutedAction.org_id == job.org_id)
        .order_by(RoutedAction.created_at.asc())
        .all()
    )

@router.post(
    "/send",
    response_model=SendMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(
    data: SendMessageRequest,
    response: Response,
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
        response.status_code = status.HTTP_200_OK
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
    sanitized_variables = sanitize_template_variables(data.variables)

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
        variables=sanitized_variables,
        country_iso=country_iso,
        status=JobStatusEnum.pending
    )
    db.add(job)

    try:
        commit_or_raise(db)
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
            response.status_code = status.HTTP_200_OK
            return SendMessageResponse(
                job_id=str(existing_job.id),
                status=existing_job.status.value,
                provider_used=None,
                estimated_cost=None,
                message="Message already processed (idempotent)",
            )

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
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
            channel=data.channel,
            contact_address=resolved_address,
            send_time=datetime.now(timezone.utc),
        )
    except ContactOptOutError as exc:
        job.status = JobStatusEnum.failed_final
        try:
            commit_or_raise(db)
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
    except RoutingPolicyViolation as exc:
        logger.info(
            "Routing policy violation on job %s for org %s", job_identifier, current_user["org_id"],
            extra={
                "event": "routing_policy_violation",
                "policy_code": exc.code,
                "detail": exc.message,
            },
        )
        job.status = JobStatusEnum.failed_final
        try:
            commit_or_raise(db)
        except Exception:
            logger.exception(
                "Failed to persist policy violation for job %s in org %s",
                job_identifier,
                current_user["org_id"],
            )
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": exc.message},
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Routing engine failure for job %s in org %s: %s",
            job_identifier,
            current_user["org_id"],
            exc,
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        job.status = JobStatusEnum.failed_final
        try:  # pragma: no cover - best effort persistence
            commit_or_raise(db)
        except Exception:
            logger.exception("Unable to mark job %s as failed after routing error", job_identifier)
        return SendMessageResponse(
            job_id=str(job_identifier),
            status=job.status.value,
            provider_used=None,
            estimated_cost=None,
            message="Routing engine error",
        )

    if not routing_decision:
        job.status = JobStatusEnum.failed_final
        try:
            commit_or_raise(db)
        except Exception:
            logger.exception("Failed to mark job %s as failed after empty routing decision", job_identifier)
        raise HTTPException(status_code=400, detail="No provider available for this route")

    estimated_cost_minor = _normalize_estimated_cost(
        routing_decision.get("estimated_cost")
    )

    baseline_cost_minor = engine.calculate_baseline_cost(
        country_iso=country_iso,
        category=data.template_category,
    )

    delivery_context = DeliveryContext(
        job_id=str(job_identifier),
        org_id=str(current_user["org_id"]),
        routing_decision=routing_decision,
        estimated_cost_minor=estimated_cost_minor,
        baseline_cost_minor=baseline_cost_minor,
        variables=data.variables,
    )

    initial_status = job.status.value

    try:
        message_worker.enqueue_message_delivery(delivery_context.to_payload())
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception(
            "Failed to enqueue delivery job %s for org %s: %s",
            job_identifier,
            current_user["org_id"],
            exc,
        )
        job.status = JobStatusEnum.failed_final
        try:
            commit_or_raise(db)
        except Exception:
            logger.exception(
                "Failed to persist enqueue failure for job %s in org %s",
                job_identifier,
                current_user["org_id"],
            )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return SendMessageResponse(
            job_id=str(job_identifier),
            status=job.status.value,
            provider_used=None,
            estimated_cost=estimated_cost_minor,
            message="Message enqueue error",
        )

    return SendMessageResponse(
        job_id=str(job_identifier),
        status=initial_status,
        provider_used=None,
        estimated_cost=estimated_cost_minor,
        message="Message enqueued for asynchronous delivery",
    )


@router.get("/jobs/{job_id}/routing", response_model=RoutedActionChainResponse)
def get_message_routing_chain(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(MessageJob)
        .filter(
            MessageJob.id == job_id,
            MessageJob.org_id == current_user["org_id"],
        )
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Message job not found")

    actions = _load_routed_actions(db, job)

    return _build_routing_chain_response(job_id=job_id, actions=actions)


@router.post(
    "/jobs/{job_id}/dry-run",
    response_model=RoutedActionChainResponse,
)
def simulate_message_delivery(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(MessageJob)
        .filter(
            MessageJob.id == job_id,
            MessageJob.org_id == current_user["org_id"],
        )
        .first()
    )

    if job is None:
        raise HTTPException(status_code=404, detail="Message job not found")

    circuit_breaker = get_circuit_breaker_store()
    dry_run_service = MessageDeliveryDryRunService(
        db,
        circuit_breaker=circuit_breaker,
    )

    try:
        result = dry_run_service.simulate(job=job)
    except ContactOptOutError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RoutingPolicyViolation as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": exc.message},
        )
    except DryRunNoRouteAvailable as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Failed to simulate delivery for job %s", job_id)
        raise HTTPException(status_code=500, detail="Failed to simulate delivery")

    actions = _load_routed_actions(db, job)
    return _build_routing_chain_response(
        job_id=job_id,
        actions=actions,
        simulation_payload=result.payload,
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
    org_uuid = coerce_uuid(org_id)
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
            "to_number": mask_contact_point(job.to_number, channel=job.channel),
            "channel": job.channel,
            "channel_address": mask_contact_point(
                job.channel_address, channel=job.channel
            ),
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
    try:
        job_uuid = UUID(str(job_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid job identifier")

    job = db.query(MessageJob).filter(
        MessageJob.id == job_uuid,
        MessageJob.org_id == current_user["org_id"]
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    attempts = (
        db.query(DeliveryAttempt, Provider)
        .join(Provider, DeliveryAttempt.provider_id == Provider.id)
        .filter(DeliveryAttempt.message_job_id == job_uuid)
        .order_by(DeliveryAttempt.attempt_number.asc())
        .all()
    )

    total_cost = (
        db.query(func.sum(CostRecord.price_eur))
        .filter(CostRecord.message_job_id == job_uuid)
        .scalar()
    )

    return {
        "id": str(job_uuid),
        "status": job.status.value,
        "to_number": mask_contact_point(job.to_number, channel=job.channel),
        "channel": job.channel,
        "channel_address": mask_contact_point(
            job.channel_address, channel=job.channel
        ),
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
