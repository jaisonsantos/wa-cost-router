from pathlib import Path
import sys

import asyncio
import httpx


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.core.config import settings  # noqa: E402
from app.services import provider_connectors  # noqa: E402
from app.services.provider_connectors import run_health_check, TwilioConnector  # noqa: E402


def test_run_health_check_success(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/Accounts/AC123.json")
        return httpx.Response(200, json={"sid": "AC123"})

    connector = TwilioConnector(
        {"account_sid": "AC123", "auth_token": "secret"},
        transport=httpx.MockTransport(handler),
    )

    monkeypatch.setattr(provider_connectors, "get_connector", lambda *args, **kwargs: connector)

    result = asyncio.run(
        run_health_check(
            "twilio",
            {"account_sid": "AC123", "auth_token": "secret"},
            provider_type="sms",
        )
    )

    assert result["healthy"] is True
    assert result["status_code"] == 200


def test_run_health_check_failure(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    connector = TwilioConnector(
        {"account_sid": "AC123", "auth_token": "secret"},
        transport=httpx.MockTransport(handler),
    )

    monkeypatch.setattr(provider_connectors, "get_connector", lambda *args, **kwargs: connector)

    result = asyncio.run(
        run_health_check(
            "twilio",
            {"account_sid": "AC123", "auth_token": "secret"},
            provider_type="sms",
        )
    )

    assert result["healthy"] is False
    assert result["status_code"] == 401
