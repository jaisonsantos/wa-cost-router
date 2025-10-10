import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.provider_connectors import SendGridConnector  # noqa: E402


def test_sendgrid_connector_sends_email_successfully():
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["payload"] = json.loads(request.content.decode())
        return httpx.Response(202, headers={"X-Message-Id": "test-message-id"})

    transport = httpx.MockTransport(handler)
    connector = SendGridConnector(
        credentials={"api_key": "test-key", "from_email": "noreply@example.com"},
        transport=transport,
    )

    result = asyncio.run(
        connector.send_message(
            to_number="user@example.com",
            template_id="d-1234567890",
            variables={"dynamic_template_data": {"first_name": "Ada"}},
        )
    )

    assert result["success"] is True
    assert result["provider_message_id"] == "test-message-id"
    assert captured_request["url"].endswith("/mail/send")
    headers = captured_request["headers"]
    assert headers.get("authorization") == "Bearer test-key" or headers.get("Authorization") == "Bearer test-key"
    payload = captured_request["payload"]
    assert payload["template_id"] == "d-1234567890"
    personalization = payload["personalizations"][0]
    assert personalization["to"][0]["email"] == "user@example.com"
    assert personalization["dynamic_template_data"] == {"first_name": "Ada"}


def test_sendgrid_connector_handles_error_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=400,
            json={"errors": [{"message": "Invalid template"}]},
        )

    transport = httpx.MockTransport(handler)
    connector = SendGridConnector(
        credentials={"api_key": "test-key", "from_email": "noreply@example.com"},
        transport=transport,
    )

    result = asyncio.run(
        connector.send_message(
            to_number="user@example.com",
            template_id="d-invalid",
            variables={},
        )
    )

    assert result["success"] is False
    assert result["error_code"] == "400"
    assert "Invalid template" in result["error_message"]


def test_sendgrid_connector_health_check_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/user/account")
        return httpx.Response(status_code=200, json={"account_id": "abc"})

    transport = httpx.MockTransport(handler)
    connector = SendGridConnector(
        credentials={"api_key": "test-key", "from_email": "noreply@example.com"},
        transport=transport,
    )

    result = asyncio.run(connector.health_check())

    assert result["healthy"] is True
    assert result["status_code"] == 200


def test_sendgrid_connector_health_check_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, json={"errors": ["Unauthorized"]})

    transport = httpx.MockTransport(handler)
    connector = SendGridConnector(
        credentials={"api_key": "test-key", "from_email": "noreply@example.com"},
        transport=transport,
    )

    result = asyncio.run(connector.health_check())

    assert result["healthy"] is False
    assert result["status_code"] == 401
    assert result["response"] == {"errors": ["Unauthorized"]}
