import asyncio
import json
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
    SandboxProviderConnector,
    WhatsAppCloudConnector,
    get_connector,
)


@pytest.fixture(autouse=True)
def reset_sandbox_flag():
    original_value = settings.SANDBOX_PROVIDERS
    yield
    settings.SANDBOX_PROVIDERS = original_value


def test_whatsapp_cloud_send_message_success():
    settings.SANDBOX_PROVIDERS = False

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/123456/messages")
        assert request.headers["Authorization"] == "Bearer token-123"
        payload = json.loads(request.content.decode())
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "+5511999999999"
        assert payload["template"]["name"] == "order_update"
        body_component = next(
            comp for comp in payload["template"]["components"] if comp["type"] == "body"
        )
        assert body_component["parameters"][0]["text"] == "42"
        return httpx.Response(200, json={"messages": [{"id": "wamid-123"}]})

    connector = WhatsAppCloudConnector(
        {"access_token": "token-123", "phone_id": "123456"},
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        connector.send_message(
            to_number="+5511999999999",
            template_id="order_update",
            variables={"language": "pt_BR", "body_params": ["42"]},
        )
    )

    assert result["success"] is True
    assert result["provider_message_id"] == "wamid-123"


def test_whatsapp_cloud_send_message_failure():
    settings.SANDBOX_PROVIDERS = False

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "(#100) Invalid parameter"}},
        )

    connector = WhatsAppCloudConnector(
        {"access_token": "token-123", "phone_id": "123456"},
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        connector.send_message(
            to_number="+5511999999999",
            template_id="order_update",
            variables={"language": "pt_BR"},
        )
    )

    assert result["success"] is False
    assert result["error_code"] == "400"
    assert result["error_message"] == "(#100) Invalid parameter"


def test_get_connector_meta_alias():
    settings.SANDBOX_PROVIDERS = False

    connector = get_connector(
        "meta",
        {"access_token": "token-123", "phone_id": "123456"},
    )

    assert isinstance(connector, WhatsAppCloudConnector)


def test_get_connector_sandbox_fallback():
    settings.SANDBOX_PROVIDERS = True

    connector = get_connector(
        "whatsapp_cloud",
        {"access_token": "token-123", "phone_id": "123456"},
    )

    assert isinstance(connector, SandboxProviderConnector)
