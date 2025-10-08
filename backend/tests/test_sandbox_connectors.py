import asyncio

from app.services.provider_connectors import (
    SandboxProviderConnector,
    get_connector,
)
from app.core.config import settings


def test_sandbox_connector_returns_success(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)
    monkeypatch.setattr(settings, "SANDBOX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "SANDBOX_FAILURE_RATE", 0.0)

    connector = get_connector("360dialog", {"access_token": "irrelevant"})
    result = asyncio.run(
        connector.send_message(
            to_number="+5511999999999",
            template_id="welcome_msg",
            variables={"language": "pt_BR"},
        )
    )

    assert result["success"] is True
    assert result["provider_message_id"].startswith("sndbx-")
    assert result["latency_ms"] == 0
    assert result["response"]["mode"] == "sandbox"


def test_sandbox_connector_failure_rate(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)
    monkeypatch.setattr(settings, "SANDBOX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "SANDBOX_FAILURE_RATE", 1.0)

    connector = get_connector("gupshup", {"api_key": "irrelevant"})
    result = asyncio.run(
        connector.send_message(
            to_number="+15555550123",
            template_id="promo_campaign",
            variables={},
        )
    )

    assert result["success"] is False
    assert result["error_code"] == "SANDBOX_FAILURE"
    assert result["response"]["mode"] == "sandbox"


def test_get_connector_real_when_sandbox_disabled(monkeypatch):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", False)

    connector = get_connector("360dialog", {"access_token": "abc"})
    assert isinstance(connector, SandboxProviderConnector) is False
