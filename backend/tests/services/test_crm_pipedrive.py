"""Testes para o conector CRM do Pipedrive."""

from datetime import datetime, timezone
from typing import Any, Dict

import httpx
import pytest

from app.services.crm import PipedriveProvider
from app.services.crm.exceptions import ProviderSyncError


class _DummyClient:
    """Cliente httpx stand-in configurável para os testes."""

    def __init__(self, response: httpx.Response, captured: Dict[str, Any]):
        self._response = response
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, params: Dict[str, Any] | None = None):
        self._captured["url"] = url
        self._captured["params"] = dict(params or {})
        return self._response


def _build_provider(credentials: Dict[str, Any]) -> PipedriveProvider:
    return PipedriveProvider(credentials)


def test_fetch_incremental_changes_normalizes_primary_fields(monkeypatch):
    credentials = {"api_token": "token", "company_domain": "example.pipedrive.com"}
    response_payload = {
        "success": True,
        "data": [
            {
                "id": 123,
                "name": "Alice Example",
                "first_name": "Alice",
                "last_name": "Example",
                "email": [
                    {"value": "alice.secondary@example.com", "primary": False},
                    {"value": "alice@example.com", "primary": True},
                ],
                "phone": [
                    {"value": "+34 9999", "primary": True},
                ],
                "update_time": "2025-01-01 10:00:00",
            },
            {
                "id": 456,
                "name": "Bob Legacy",
                "email": [],
                "phone": [],
                "update_time": "2024-12-31 23:59:59",
            },
        ],
        "additional_data": {
            "pagination": {
                "start": 0,
                "limit": 200,
                "more_items_in_collection": True,
                "next_start": 200,
            }
        },
    }
    captured: Dict[str, Any] = {}
    dummy_response = httpx.Response(200, json=response_payload)

    def _client_factory(*args, **kwargs):
        return _DummyClient(dummy_response, captured)

    monkeypatch.setattr(httpx, "Client", _client_factory)

    provider = _build_provider(credentials)
    since = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc)

    result = provider.fetch_incremental_changes(since=since, cursor=None, page_size=200)

    assert captured["url"] == "https://example.pipedrive.com/api/v1/persons"
    assert captured["params"]["api_token"] == "token"
    assert captured["params"]["limit"] == 200
    assert captured["params"]["sort"] == "update_time ASC"

    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.external_id == "123"
    assert change.data["primary_email"] == "alice@example.com"
    assert change.data["primary_phone"] == "+34 9999"
    assert change.data["id"] == "123"
    assert change.changed_at > since
    assert change.change_id.startswith("123:")

    assert result.next_cursor == "200"
    assert result.has_more is True


def test_fetch_incremental_changes_raises_on_http_error(monkeypatch):
    credentials = {"api_token": "token", "company_domain": "acme.pipedrive.com"}
    dummy_response = httpx.Response(401, json={"success": False, "message": "Unauthorized"})

    def _client_factory(*args, **kwargs):
        return _DummyClient(dummy_response, {})

    monkeypatch.setattr(httpx, "Client", _client_factory)

    provider = _build_provider(credentials)

    with pytest.raises(ProviderSyncError):
        provider.fetch_incremental_changes(since=None, cursor=None, page_size=50)


def test_fetch_incremental_changes_raises_on_success_false(monkeypatch):
    credentials = {"api_token": "token", "company_domain": "acme.pipedrive.com"}
    dummy_response = httpx.Response(200, json={"success": False, "error": "maintenance"})

    def _client_factory(*args, **kwargs):
        return _DummyClient(dummy_response, {})

    monkeypatch.setattr(httpx, "Client", _client_factory)

    provider = _build_provider(credentials)

    with pytest.raises(ProviderSyncError):
        provider.fetch_incremental_changes(since=None, cursor=None, page_size=50)


def test_fetch_incremental_changes_uses_cursor_parameter(monkeypatch):
    credentials = {"api_token": "token", "company_domain": "acme.pipedrive.com"}
    response_payload = {
        "success": True,
        "data": [],
        "additional_data": {"pagination": {"more_items_in_collection": False}},
    }
    captured: Dict[str, Any] = {}
    dummy_response = httpx.Response(200, json=response_payload)

    def _client_factory(*args, **kwargs):
        return _DummyClient(dummy_response, captured)

    monkeypatch.setattr(httpx, "Client", _client_factory)

    provider = _build_provider(credentials)
    provider.fetch_incremental_changes(since=None, cursor="50", page_size=10)

    assert captured["params"]["start"] == 50


def test_configure_webhook_not_supported():
    provider = _build_provider({"api_token": "token", "company_domain": "beta.pipedrive.com"})

    with pytest.raises(ProviderSyncError):
        provider.configure_webhook("https://callback", "secret")


def test_missing_company_domain_raises_error():
    with pytest.raises(ProviderSyncError):
        _build_provider({"api_token": "token"})
