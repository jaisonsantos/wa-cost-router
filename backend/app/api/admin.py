import logging
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from app.core.circuit_breaker import get_circuit_breaker_store
from app.core.config import settings

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

def require_admin_metrics_token(
    provided_token: str | None = Header(default=None, alias=settings.METRICS_AUTH_HEADER_NAME),
) -> None:
    expected_token = settings.get_metrics_auth_token()
    if not expected_token:
        logger.error(
            "Metrics authentication missing", extra={"event": "admin_metrics_auth_missing"}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics authentication is not configured",
        )

    if provided_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin auth token",
        )

    if not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin auth token",
        )


@router.get("/metrics")
def metrics(_: None = Depends(require_admin_metrics_token)):
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
