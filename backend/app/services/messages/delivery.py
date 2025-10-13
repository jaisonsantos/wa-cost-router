from __future__ import annotations

import asyncio
import logging
import uuid
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from prometheus_client import Counter, Gauge
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.circuit_breaker import CircuitBreakerStore, CircuitState
from app.core.pii import sanitize_provider_payload
from app.core.security import decrypt_credentials
from app.models.models import (
    AttemptStatusEnum,
    CostRecord,
    DeliveryAttempt,
    JobStatusEnum,
    MessageEvent,
    MessageJob,
    Provider,
    ProviderCredential,
    RateCard,
    RoutedAction,
)
from app.services.conversations import ConversationLifecycleService
from app.services.provider_connectors import get_connector
from app.services.routing_engine import RoutingEngine


logger = logging.getLogger(__name__)


MESSAGES_SEND_COUNTER = Counter(
    "messages_send_total",
    "Total de requisições /messages/send processadas",
    labelnames=["status", "provider", "channel"],
)

DELIVERY_ATTEMPTS_COUNTER = Counter(
    "messages_delivery_attempts_total",
    "Total de tentativas de entrega por provedor",
    labelnames=["provider_id", "provider", "outcome", "channel"],
)

CIRCUIT_STATE_GAUGE = Gauge(
    "messages_circuit_breaker_state",
    "Estado atual do circuito por provedor (0=closed,1=half-open,2=open)",
    labelnames=["provider_id"],
)


@dataclass
class DeliveryContext:
    job_id: str
    org_id: str
    routing_decision: Dict[str, Any]
    estimated_cost_minor: int
    baseline_cost_minor: int
    variables: Optional[Dict[str, Any]] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "org_id": self.org_id,
            "routing_decision": self.routing_decision,
            "estimated_cost_minor": self.estimated_cost_minor,
            "baseline_cost_minor": self.baseline_cost_minor,
        }
        if self.variables is not None:
            payload["variables"] = copy.deepcopy(self.variables)
        return payload

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "DeliveryContext":
        variables = payload.get("variables")
        if variables is not None:
            variables = copy.deepcopy(variables)
        return cls(
            job_id=str(payload.get("job_id")),
            org_id=str(payload.get("org_id")),
            routing_decision=dict(payload.get("routing_decision") or {}),
            estimated_cost_minor=int(payload.get("estimated_cost_minor", 0) or 0),
            baseline_cost_minor=int(payload.get("baseline_cost_minor", 0) or 0),
            variables=variables,
        )


@dataclass
class DeliveryResult:
    job_id: str
    status: str
    provider_name: Optional[str]
    message: str
    channel: Optional[str]


class DryRunNoRouteAvailable(RuntimeError):
    """Raised when the routing engine cannot determine a provider for the job."""


class MessageDeliveryDryRunService:
    """Reconstroi o contexto de entrega sem alterar o estado persistido."""

    def __init__(
        self,
        db: Session,
        circuit_breaker: Optional[CircuitBreakerStore] = None,
    ) -> None:
        self.db = db
        self.circuit_breaker = circuit_breaker

    def simulate(self, *, job: MessageJob) -> DeliveryContext:
        engine = RoutingEngine(
            self.db,
            job.org_id,
            circuit_breaker=self.circuit_breaker,
        )

        routing_decision = engine.select_provider(
            country_iso=job.country_iso or "XX",
            category=job.template_category or "",
            template_id=job.template_id,
            channel=job.channel,
            contact_address=job.channel_address or job.to_number,
            send_time=datetime.now(timezone.utc),
        )

        if not routing_decision:
            raise DryRunNoRouteAvailable("No provider available for this job")

        estimated_cost_minor = self._normalize_estimated_cost(
            routing_decision.get("estimated_cost")
        )
        baseline_cost_minor = engine.calculate_baseline_cost(
            job.country_iso or "XX",
            job.template_category or "",
        )

        context = DeliveryContext(
            job_id=str(job.id),
            org_id=str(job.org_id),
            routing_decision=dict(routing_decision),
            estimated_cost_minor=estimated_cost_minor,
            baseline_cost_minor=baseline_cost_minor,
            variables=copy.deepcopy(job.variables) if job.variables else None,
        )

        primary_identifier = routing_decision.get("provider_id")
        fallback_identifiers = self._normalize_fallback_chain(
            routing_decision.get("fallback_chain")
        )
        ordered_identifiers = []
        if primary_identifier is not None:
            ordered_identifiers.append(str(primary_identifier))
        ordered_identifiers.extend(fallback_identifiers)

        provider_names = self._load_provider_names(ordered_identifiers)

        dry_run_payload = sanitize_provider_payload(
            {
                "job_id": str(job.id),
                "dry_run": True,
                "rule_name": routing_decision.get("rule_name"),
                "rule_id": routing_decision.get("rule_id"),
                "provider_id": str(primary_identifier) if primary_identifier else None,
                "provider_name": provider_names.get(str(primary_identifier))
                if primary_identifier
                else None,
                "fallback_chain": [
                    {
                        "provider_id": identifier,
                        "provider_name": provider_names.get(identifier),
                    }
                    for identifier in fallback_identifiers
                ],
                "estimated_cost_minor": estimated_cost_minor,
                "baseline_cost_minor": baseline_cost_minor,
            }
        )

        dry_run_action = RoutedAction(
            org_id=job.org_id,
            rule_id=coerce_uuid(routing_decision.get("rule_id")),
            message_event_id=None,
            action="deliver_message",
            status="dry_run",
            provider_response=dry_run_payload,
            cost_minor=estimated_cost_minor,
            dry_run=True,
        )
        self.db.add(dry_run_action)
        commit_or_raise(self.db)

        return context

    def _normalize_fallback_chain(self, fallback_chain: Any) -> list[str]:
        if fallback_chain in (None, ""):
            return []
        if isinstance(fallback_chain, Iterable) and not isinstance(
            fallback_chain, (str, bytes)
        ):
            normalized: list[str] = []
            for candidate in fallback_chain:
                if candidate is None:
                    continue
                normalized.append(str(candidate))
            return normalized
        logger.warning("Invalid fallback chain %r; ignoring", fallback_chain)
        return []

    def _load_provider_names(self, identifiers: list[str]) -> Dict[str, Optional[str]]:
        if not identifiers:
            return {}

        uuid_identifiers = [coerce_uuid(identifier) for identifier in identifiers]
        valid_ids = [identifier for identifier in uuid_identifiers if identifier]
        if not valid_ids:
            return {}

        rows = (
            self.db.query(Provider.id, Provider.name)
            .filter(Provider.id.in_(valid_ids))
            .all()
        )
        return {str(row.id): row.name for row in rows}

    @staticmethod
    def _normalize_estimated_cost(value: Any) -> int:
        if value is None:
            return 0
        try:
            cost = int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid estimated cost %r; defaulting to 0", value)
            return 0
        return max(cost, 0)


class MessageDeliveryService:
    """Coordena o envio de mensagens utilizando provedor principal e fallback."""

    def __init__(self, db: Session, circuit_breaker: CircuitBreakerStore) -> None:
        self.db = db
        self.circuit_breaker = circuit_breaker

    def _ensure_unique_provider_event_id(self, provider_event_id: str) -> str:
        candidate = provider_event_id
        suffix = 1
        while (
            self.db.query(MessageEvent.id)
            .filter(MessageEvent.provider_event_id == candidate)
            .first()
        ):
            candidate = f"{provider_event_id}-{suffix}"
            suffix += 1
        return candidate

    async def deliver(self, context: DeliveryContext) -> DeliveryResult:
        job_uuid = coerce_uuid(context.job_id)
        org_uuid = coerce_uuid(context.org_id)

        if job_uuid is None or org_uuid is None:
            logger.error(
                "Invalid delivery context: job_id=%s org_id=%s", context.job_id, context.org_id
            )
            return DeliveryResult(
                job_id=context.job_id,
                status=JobStatusEnum.failed_final.value,
                provider_name=None,
                message="Invalid delivery context",
                channel=None,
            )

        job = self.db.get(MessageJob, job_uuid)
        if job is None:
            logger.error("Message job %s not found for delivery", context.job_id)
            return DeliveryResult(
                job_id=context.job_id,
                status=JobStatusEnum.failed_final.value,
                provider_name=None,
                message="Message job not found",
                channel=None,
            )

        if job.org_id != org_uuid:
            logger.warning(
                "Mismatch org context for job %s: expected %s got %s",
                context.job_id,
                org_uuid,
                job.org_id,
            )
            job.status = JobStatusEnum.failed_final
            self._record_failure_action(
                job=job,
                rule_id=None,
                rule_name=None,
                reason="invalid_org_context",
                cost_minor=context.estimated_cost_minor,
            )
            commit_or_raise(self.db)
            return DeliveryResult(
                job_id=context.job_id,
                status=job.status.value,
                provider_name=None,
                message="Invalid organization context",
                channel=job.channel,
            )

        rule_id = coerce_uuid(context.routing_decision.get("rule_id"))
        rule_name = context.routing_decision.get("rule_name")

        providers_to_try = self._build_provider_chain(context.routing_decision)

        attempt_number = 0
        final_provider: Optional[str] = None
        last_attempt_cost = context.estimated_cost_minor

        for provider_id in providers_to_try:
            attempt_number += 1

            provider = (
                self.db.query(Provider)
                .filter(Provider.id == provider_id, Provider.org_id == org_uuid)
                .first()
            )
            if not provider:
                logger.warning("Provider %s not found for org %s", provider_id, org_uuid)
                continue

            state = self.circuit_breaker.get_state(str(provider.id))
            record_circuit_state(provider.id, state)
            if state.is_blocked():
                logger.info(
                    "Skipping provider %s attempt %s due to circuit state %s",
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
                    channel=job.channel,
                ).inc()
                continue

            credential = (
                self.db.query(ProviderCredential)
                .filter(
                    ProviderCredential.org_id == org_uuid,
                    ProviderCredential.provider_id == provider_id,
                    ProviderCredential.is_active.is_(True),
                )
                .first()
            )

            if not credential:
                logger.warning("No credentials for provider %s", provider_id)
                continue

            try:
                credentials_payload = decrypt_credentials(credential.credentials_encrypted)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error("Invalid credentials payload for provider %s: %s", provider_id, exc)
                continue

            attempt_cost_minor, attempt_currency = resolve_pricing_context(
                db=self.db,
                provider_id=provider.id,
                country_iso=job.country_iso,
                category=job.template_category,
                fallback_cost=context.estimated_cost_minor,
            )
            last_attempt_cost = attempt_cost_minor

            for retry in range(3):
                connector = get_connector(
                    provider.name,
                    credentials_payload,
                    provider.base_url,
                    provider_type=provider.type,
                )

                send_variables = context.variables if context.variables is not None else (job.variables or {})

                try:
                    result = await connector.send_message(
                        to_number=job.channel_address,
                        template_id=job.template_id,
                        variables=send_variables,
                    )
                except Exception as exc:  # pragma: no cover - network/connector errors
                    logger.error("Delivery error for provider %s: %s", provider.id, exc)
                    self._record_attempt(
                        job=job,
                        provider=provider,
                        attempt_number=attempt_number,
                        status=AttemptStatusEnum.failed,
                        rule_id=rule_id,
                        rule_name=rule_name,
                        retry=retry,
                        cost_minor=attempt_cost_minor,
                        payload={
                            "error": str(exc),
                        },
                    )
                    commit_or_raise(self.db)

                    new_state = self.circuit_breaker.mark_failure(str(provider.id))
                    record_circuit_state(provider.id, new_state)
                    log_circuit_transition(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        state=new_state,
                        reason="exception",
                    )
                    DELIVERY_ATTEMPTS_COUNTER.labels(
                        provider_id=str(provider.id),
                        provider=provider.name,
                        outcome="exception",
                        channel=job.channel,
                    ).inc()
                    break

                attempt_status = (
                    AttemptStatusEnum.success if result.get("success") else AttemptStatusEnum.failed
                )

                attempt = DeliveryAttempt(
                    message_job_id=job.id,
                    provider_id=provider.id,
                    attempt_number=attempt_number,
                    status=attempt_status,
                    error_code=result.get("error_code"),
                    error_message=result.get("error_message"),
                    latency_ms=result.get("latency_ms"),
                    provider_message_id=result.get("provider_message_id"),
                    provider_response=sanitize_provider_payload(result.get("response")),
                )
                self.db.add(attempt)

                if result.get("success"):
                    new_state = self.circuit_breaker.mark_success(str(provider.id))
                    record_circuit_state(provider.id, new_state)
                    log_circuit_transition(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        state=new_state,
                        reason="success",
                    )

                    cost_record = CostRecord(
                        message_job_id=job.id,
                        provider_id=provider.id,
                        price_eur=attempt_cost_minor,
                        country_iso=job.country_iso,
                        category=job.template_category,
                        price_table_version="v1",
                    )
                    self.db.add(cost_record)

                    provider_message_id = result.get("provider_message_id")
                    if not provider_message_id:
                        provider_message_id = f"job-{job.id}-attempt-{attempt_number}"
                    provider_message_id = self._ensure_unique_provider_event_id(
                        str(provider_message_id)
                    )

                    event_attributes = {
                        "routing_rule_id": str(rule_id) if rule_id else None,
                        "routing_rule_name": rule_name,
                        "provider_id": str(provider.id),
                    }
                    event_attributes = {k: v for k, v in event_attributes.items() if v is not None}

                    message_event = MessageEvent(
                        id=uuid.uuid4(),
                        org_id=job.org_id,
                        message_job_id=job.id,
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
                        unit_cost_minor=attempt_cost_minor,
                        baseline_cost_minor=context.baseline_cost_minor,
                        currency=attempt_currency,
                        attributes=event_attributes or None,
                    )
                    self.db.add(message_event)

                    lifecycle_service = ConversationLifecycleService(self.db)
                    lifecycle_service.handle_outbound(
                        org_id=job.org_id,
                        channel=job.channel,
                        channel_address=job.channel_address or job.to_number,
                        contact_id=job.contact_id,
                        occurred_at=message_event.timestamp_provider,
                    )

                    job.status = (
                        JobStatusEnum.delivered
                        if attempt_number == 1
                        else JobStatusEnum.delivered_with_fallback
                    )

                    success_action = RoutedAction(
                        org_id=job.org_id,
                        rule_id=rule_id,
                        message_event_id=message_event.id,
                        action="deliver_message",
                        status=job.status.value,
                        provider_response=sanitize_provider_payload(
                            {
                                "job_id": str(job.id),
                                "rule_name": rule_name,
                                "provider_id": str(provider.id),
                                "provider_name": provider.name,
                                "attempt_number": attempt_number,
                                "connector_response": result.get("response"),
                                "provider_message_id": provider_message_id,
                            }
                        ),
                        cost_minor=attempt_cost_minor,
                    )
                    self.db.add(success_action)

                    commit_or_raise(self.db)

                    DELIVERY_ATTEMPTS_COUNTER.labels(
                        provider_id=str(provider.id),
                        provider=provider.name,
                        outcome="success",
                        channel=job.channel,
                    ).inc()

                    final_provider = provider.name
                    return DeliveryResult(
                        job_id=str(job.id),
                        status=job.status.value,
                        provider_name=provider.name,
                        message="Message delivered successfully",
                        channel=job.channel,
                    )

                failure_payload = sanitize_provider_payload(
                    {
                        "job_id": str(job.id),
                        "rule_name": rule_name,
                        "provider_id": str(provider.id),
                        "provider_name": provider.name,
                        "attempt_number": attempt_number,
                        "connector_response": result.get("response"),
                        "error_code": result.get("error_code"),
                        "error_message": result.get("error_message"),
                    }
                )

                failure_action = RoutedAction(
                    org_id=job.org_id,
                    rule_id=rule_id,
                    message_event_id=None,
                    action="deliver_message",
                    status=attempt_status.value,
                    provider_response=failure_payload,
                    cost_minor=attempt_cost_minor,
                )
                self.db.add(failure_action)

                try:
                    commit_or_raise(self.db)
                except Exception:
                    logger.exception("Failed to persist failed attempt for provider %s", provider.id)
                    raise

                if result.get("error_code") in ["429", "timeout"]:
                    await asyncio.sleep(2 ** retry)
                    continue

                new_state = self.circuit_breaker.mark_failure(str(provider.id))
                record_circuit_state(provider.id, new_state)
                log_circuit_transition(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    state=new_state,
                    reason="failure",
                )
                DELIVERY_ATTEMPTS_COUNTER.labels(
                    provider_id=str(provider.id),
                    provider=provider.name,
                    outcome="failure",
                    channel=job.channel,
                ).inc()

                break

        job.status = JobStatusEnum.failed_final
        self._record_failure_action(
            job=job,
            rule_id=rule_id,
            rule_name=rule_name,
            reason="all_providers_failed",
            cost_minor=last_attempt_cost,
        )
        commit_or_raise(self.db)

        return DeliveryResult(
            job_id=str(job.id),
            status=job.status.value,
            provider_name=final_provider,
            message="All providers failed",
            channel=job.channel,
        )

    def _record_failure_action(
        self,
        *,
        job: MessageJob,
        rule_id: Optional[uuid.UUID],
        rule_name: Optional[str],
        reason: str,
        cost_minor: int,
    ) -> None:
        failure_action = RoutedAction(
            org_id=job.org_id,
            rule_id=rule_id,
            message_event_id=None,
            action="deliver_message",
            status=JobStatusEnum.failed_final.value,
            provider_response=sanitize_provider_payload(
                {
                    "job_id": str(job.id),
                    "rule_name": rule_name,
                    "provider_id": None,
                    "provider_name": None,
                    "reason": reason,
                }
            ),
            cost_minor=cost_minor,
        )
        self.db.add(failure_action)

    def _record_attempt(
        self,
        *,
        job: MessageJob,
        provider: Provider,
        attempt_number: int,
        status: AttemptStatusEnum,
        rule_id: Optional[uuid.UUID],
        rule_name: Optional[str],
        retry: int,
        cost_minor: int,
        payload: Dict[str, Any],
    ) -> None:
        attempt = DeliveryAttempt(
            message_job_id=job.id,
            provider_id=provider.id,
            attempt_number=attempt_number,
            status=status,
            error_code="EXCEPTION",
            error_message=payload.get("error"),
        )
        self.db.add(attempt)

        action = RoutedAction(
            org_id=job.org_id,
            rule_id=rule_id,
            message_event_id=None,
            action="deliver_message",
            status=status.value,
            provider_response=sanitize_provider_payload(
                {
                    "job_id": str(job.id),
                    "rule_name": rule_name,
                    "provider_id": str(provider.id),
                    "provider_name": provider.name,
                    "attempt_number": attempt_number,
                    "retry": retry,
                    **payload,
                }
            ),
            cost_minor=cost_minor,
        )
        self.db.add(action)

    @staticmethod
    def _build_provider_chain(routing_decision: Dict[str, Any]) -> Iterable[uuid.UUID]:
        raw_providers: list[Any] = []
        primary_identifier = routing_decision.get("provider_id")
        if primary_identifier is not None:
            raw_providers.append(primary_identifier)

        fallback_chain = routing_decision.get("fallback_chain")
        if fallback_chain in (None, ""):
            fallback_candidates: Iterable[Any] = []
        elif isinstance(fallback_chain, Iterable) and not isinstance(
            fallback_chain, (str, bytes)
        ):
            fallback_candidates = fallback_chain
        else:
            logger.warning("Invalid fallback chain %r; ignoring", fallback_chain)
            fallback_candidates = []

        raw_providers.extend(list(fallback_candidates))

        for raw_identifier in raw_providers:
            provider_uuid = coerce_uuid(raw_identifier)
            if provider_uuid is None:
                logger.warning("Skipping invalid provider identifier %r", raw_identifier)
                continue
            yield provider_uuid


def coerce_uuid(value: Any) -> Optional[uuid.UUID]:
    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def resolve_pricing_context(
    *,
    db: Session,
    provider_id: uuid.UUID,
    country_iso: Optional[str],
    category: Optional[str],
    fallback_cost: int,
) -> Tuple[int, Optional[str]]:
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


def commit_or_raise(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise exc
    except Exception:
        db.rollback()
        raise


def record_circuit_state(provider_id: uuid.UUID | str, state: CircuitState) -> None:
    try:
        value_map = {"closed": 0, "half-open": 1, "open": 2}
        CIRCUIT_STATE_GAUGE.labels(provider_id=str(provider_id)).set(value_map.get(state.state, 0))
    except Exception:  # pragma: no cover - metrics failures must not break worker
        logger.exception(
            "Failed to record circuit state metric",
            extra={"event": "metrics_error", "metric": "messages_circuit_breaker_state"},
        )


def log_circuit_transition(
    *,
    provider_id: uuid.UUID | str,
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


__all__ = [
    "DeliveryContext",
    "DeliveryResult",
    "DryRunNoRouteAvailable",
    "MessageDeliveryDryRunService",
    "MessageDeliveryService",
    "MESSAGES_SEND_COUNTER",
    "DELIVERY_ATTEMPTS_COUNTER",
    "CIRCUIT_STATE_GAUGE",
    "commit_or_raise",
    "coerce_uuid",
    "resolve_pricing_context",
    "record_circuit_state",
    "log_circuit_transition",
]

