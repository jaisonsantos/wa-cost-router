import asyncio
import sys
from pathlib import Path

import httpx
import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.core.config import settings  # noqa: E402
from app.services.provider_connectors import (  # noqa: E402
    TwilioConnector,
    get_connector,
)


def test_twilio_send_message_success(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "Accounts/AC123/Messages.json" in request.url.path
        payload = dict(httpx.QueryParams(request.content.decode()))
        assert payload["To"] == "+15551234567"
        assert payload["From"] == "+15557654321"
        assert payload["Body"] == "Hello"
        return httpx.Response(
            201,
            json={"sid": "SM123", "status": "queued"},
        )

    connector = TwilioConnector(
        {
            "account_sid": "AC123",
            "auth_token": "secret",
            "from_number": "+15557654321",
        },
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        connector.send_message(
            to_number="+15551234567",
            template_id="ignored",
            variables={"body": "Hello"},
        )
    )

    assert result["success"] is True
    assert result["provider_message_id"] == "SM123"
    assert result["response"]["status"] == "queued"


def test_twilio_send_message_failure(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "Invalid To number"})

    connector = TwilioConnector(
        {
            "account_sid": "AC123",
            "auth_token": "secret",
            "from_number": "+15557654321",
        },
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        connector.send_message(
            to_number="+15551234567",
            template_id="ignored",
            variables={"body": "Hello"},
        )
    )

    assert result["success"] is False
    assert result["error_code"] == "400"
    assert result["error_message"] == "Invalid To number"


def test_twilio_sandbox_connector_overrides(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)

    connector = get_connector(
        "twilio",
        credentials={},
        sandbox_options={"latency_ms": 0, "failure_rate": 1.0},
    )

    result = asyncio.run(
        connector.send_message(
            to_number="+15551234567",
            template_id="ignored",
            variables={"body": "Hello"},
        )
    )

    assert result["success"] is False
    assert result["error_code"] == "SANDBOX_FAILURE"
    assert result["latency_ms"] == 0
