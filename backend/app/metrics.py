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
