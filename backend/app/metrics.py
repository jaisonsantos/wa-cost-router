"""Centralized Prometheus metrics for the backend services."""

from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


SLA_FIRST_RESPONSE_SECONDS = Histogram(
    "sla_first_response_seconds",
    "Latência em segundos até a primeira resposta por canal",
    labelnames=["channel"],
    buckets=(30, 60, 120, 300, 600, 900, 1800),
)

SLA_FIRST_RESPONSE_TRACKED_COUNTER = Counter(
    "sla_first_response_tracked_total",
    "Total de conversas com SLA de primeira resposta monitorado",
    labelnames=["channel"],
)

SLA_FIRST_RESPONSE_WITHIN_TARGET_COUNTER = Counter(
    "sla_first_response_within_target_total",
    "Total de conversas que cumpriram o SLA de primeira resposta",
    labelnames=["channel"],
)

SLA_FIRST_RESPONSE_TARGET_SECONDS = Gauge(
    "sla_first_response_target_seconds",
    "SLA configurado de primeira resposta por canal",
    labelnames=["channel"],
)

BILLING_USAGE_RECORDS_COUNTER = Counter(
    "billing_usage_records_total",
    "Total de chamadas Stripe UsageRecord por status",
    labelnames=["org_id", "status"],
)

BILLING_TAX_APPLIED_TOTAL = Gauge(
    "billing_tax_applied_total",
    "Total acumulado (em minor units) de impostos cobrados por organização",
    labelnames=["org_id"],
)

BILLING_RECONCILE_DRIFT = Gauge(
    "billing_reconcile_drift",
    "Último percentual de divergência detectado na reconciliação de invoices",
    labelnames=["org_id"],
)


def record_first_response_latency(
    channel: str,
    latency_seconds: Optional[int],
    *,
    target_seconds: Optional[int] = None,
) -> None:
    """Observa métricas de SLA para a primeira resposta por canal."""

    if latency_seconds is None:
        return

    labels = {"channel": channel}

    try:
        SLA_FIRST_RESPONSE_SECONDS.labels(**labels).observe(float(latency_seconds))
        SLA_FIRST_RESPONSE_TRACKED_COUNTER.labels(**labels).inc()

        if target_seconds is not None:
            SLA_FIRST_RESPONSE_TARGET_SECONDS.labels(**labels).set(float(target_seconds))
            if latency_seconds <= target_seconds:
                SLA_FIRST_RESPONSE_WITHIN_TARGET_COUNTER.labels(**labels).inc()
    except Exception:  # pragma: no cover - métricas não devem quebrar o fluxo
        logger.exception(
            "Failed to record first response SLA metrics",
            extra={"event": "metrics_error", "metric": "sla_first_response"},
        )


def record_billing_usage_sync(org_id: str, status: str) -> None:
    """Incrementa contadores de usage record enviados ao Stripe."""

    try:
        BILLING_USAGE_RECORDS_COUNTER.labels(org_id=org_id, status=status).inc()
    except Exception:  # pragma: no cover - métricas não devem quebrar o fluxo
        logger.exception(
            "Failed to record billing usage metric",
            extra={"event": "metrics_error", "metric": "billing_usage_records", "org_id": org_id, "status": status},
        )


def record_billing_tax_total(org_id: str, amount_minor: int) -> None:
    """Atualiza o total acumulado de impostos aplicados para uma organização."""

    try:
        BILLING_TAX_APPLIED_TOTAL.labels(org_id=org_id).set(float(amount_minor))
    except Exception:  # pragma: no cover - métricas não devem quebrar o fluxo
        logger.exception(
            "Failed to record billing tax metric",
            extra={
                "event": "metrics_error",
                "metric": "billing_tax_applied_total",
                "org_id": org_id,
                "amount_minor": amount_minor,
            },
        )


def record_billing_reconcile_drift(org_id: str, drift_pct: float) -> None:
    """Registra o último drift percentual encontrado na reconciliação de invoices."""

    try:
        BILLING_RECONCILE_DRIFT.labels(org_id=org_id).set(float(drift_pct))
    except Exception:  # pragma: no cover - métricas não devem quebrar o fluxo
        logger.exception(
            "Failed to record billing reconcile drift",
            extra={
                "event": "metrics_error",
                "metric": "billing_reconcile_drift",
                "org_id": org_id,
                "drift_pct": drift_pct,
            },
        )
