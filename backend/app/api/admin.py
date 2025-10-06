from fastapi import APIRouter
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

router = APIRouter()

request_count = Counter("app_requests_total", "Total requests")

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/metrics")
def metrics():
    request_count.inc()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
