import contextlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin
from app.core.config import settings


def build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(admin.router, prefix="/admin")
    return test_app


@contextlib.contextmanager
def override_metrics_token(token: str | None, environment: str = "test"):
    original_token = settings.METRICS_AUTH_TOKEN
    original_env = settings.ENVIRONMENT
    original_local = settings.METRICS_AUTH_LOCAL_TOKEN
    try:
        settings.METRICS_AUTH_TOKEN = token
        settings.ENVIRONMENT = environment
        settings.METRICS_AUTH_LOCAL_TOKEN = "test-admin-metrics-token"
        yield
    finally:
        settings.METRICS_AUTH_TOKEN = original_token
        settings.ENVIRONMENT = original_env
        settings.METRICS_AUTH_LOCAL_TOKEN = original_local


def test_metrics_without_token_returns_401():
    with override_metrics_token("expected-token"):
        with TestClient(build_test_app()) as client:
            response = client.get("/admin/metrics")
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing admin auth token"}


def test_metrics_with_invalid_token_returns_403():
    with override_metrics_token("expected-token"):
        with TestClient(build_test_app()) as client:
            response = client.get(
                "/admin/metrics",
                headers={settings.METRICS_AUTH_HEADER_NAME: "wrong"},
            )
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid admin auth token"}


def test_metrics_with_valid_token_succeeds():
    with override_metrics_token("expected-token"):
        with TestClient(build_test_app()) as client:
            response = client.get(
                "/admin/metrics",
                headers={settings.METRICS_AUTH_HEADER_NAME: "expected-token"},
            )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
