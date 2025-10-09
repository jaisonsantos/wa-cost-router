import logging
import time

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from app.core.circuit_breaker import get_circuit_breaker_store

router = APIRouter()

logger = logging.getLogger(__name__)

request_count = Counter("app_requests_total", "Total requests")
metrics_scrape_count = Counter("admin_metrics_scrapes_total", "Total de scrapes no endpoint /admin/metrics")
metrics_last_scrape = Gauge("admin_metrics_last_scrape_timestamp", "Timestamp da última coleta de métricas")
circuit_open_gauge = Gauge("admin_circuit_breakers_open_total", "Quantidade de circuitos em estado open")
circuit_half_open_gauge = Gauge("admin_circuit_breakers_half_open_total", "Quantidade de circuitos em estado half-open")

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/metrics")
def metrics():
    request_count.inc()
    metrics_scrape_count.inc()
    try:
        counts = get_circuit_breaker_store().count_by_state()
        circuit_open_gauge.set(counts.get("open", 0))
        circuit_half_open_gauge.set(counts.get("half-open", 0))
    except Exception:  # pragma: no cover - metrics failures must not impact endpoint
        logger.exception("Failed to update circuit breaker gauges", extra={"event": "metrics_error"})
    finally:
        metrics_last_scrape.set(time.time())

    logger.info(
        "Prometheus scrape served",
        extra={"event": "admin_metrics_scrape"},
    )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
