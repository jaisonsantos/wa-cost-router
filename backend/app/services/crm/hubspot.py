"""Provedor CRM para HubSpot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from .base import CRMContactChange, CRMIncrementalResult, CRMProvider
from .exceptions import ProviderSyncError


def _parse_timestamp(raw: Any) -> datetime:
    """Converte diferentes formatos de timestamp HubSpot para datetime."""

    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc)
    if isinstance(raw, (int, float)):
        # HubSpot envia milissegundos
        return datetime.fromtimestamp(float(raw) / 1000, tz=timezone.utc)
    if isinstance(raw, str):
        normalized = raw.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized).astimezone(timezone.utc)
        except ValueError:
            pass
        if normalized.isdigit():
            return datetime.fromtimestamp(int(normalized) / 1000, tz=timezone.utc)
    return datetime.now(timezone.utc)


class HubSpotProvider(CRMProvider):
    """Implementação do conector HubSpot."""

    slug = "hubspot"
    display_name = "HubSpot CRM"
    default_field_mapping = {
        "external_id": "id",
        "email": "properties.email",
        "phone": "properties.phone",
        "first_name": "properties.firstname",
        "last_name": "properties.lastname",
        "full_name": "properties.firstname",  # recombinado no serviço
    }

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = credentials.get("base_url", "https://api.hubapi.com")
        token = credentials.get("access_token") or credentials.get("private_app_token")
        if not token:
            raise ProviderSyncError(self.slug, "Token de acesso não informado nas credenciais.")
        self._auth_header = {"Authorization": f"Bearer {token}"}
        self._http_timeout = credentials.get("timeout", 30.0)

    def configure_webhook(self, callback_url: str, secret: str) -> None:
        payload = {
            "enabled": True,
            "secret": secret,
            "url": callback_url,
        }
        app_id = self.credentials.get("app_id")
        if app_id:
            payload["appId"] = app_id

        endpoint = f"{self.base_url}/crm/v3/extensions/webhooks/settings"
        with httpx.Client(timeout=self._http_timeout) as client:
            response = client.patch(endpoint, headers=self._auth_header, json=payload)

        if response.status_code >= 400:
            raise ProviderSyncError(self.slug, f"Falha ao configurar webhook: {response.text}")

    def parse_outbound_webhook(self, payload: Dict[str, Any]) -> List[CRMContactChange]:
        events = payload.get("events") or []
        changes: List[CRMContactChange] = []
        for event in events:
            object_type = str(event.get("objectType") or event.get("subscriptionType", "")).lower()
            if "contact" not in object_type:
                continue

            contact_id = str(event.get("objectId") or event.get("id"))
            if not contact_id:
                continue

            occurred_at = _parse_timestamp(
                event.get("occurredAt")
                or event.get("eventOccurredAt")
                or event.get("timestamp")
            )
            properties = event.get("properties") or {}
            if not properties and "propertyName" in event and "propertyValue" in event:
                properties = {event["propertyName"]: event["propertyValue"]}

            normalized_payload = {
                "id": contact_id,
                "properties": properties,
            }

            changes.append(
                CRMContactChange(
                    external_id=contact_id,
                    changed_at=occurred_at,
                    data=normalized_payload,
                    change_type="upsert",
                    origin="webhook",
                    change_id=str(event.get("eventId") or event.get("subscriptionId") or ""),
                    raw_payload=event,
                )
            )

        return changes

    def fetch_incremental_changes(
        self,
        *,
        since: Optional[datetime],
        cursor: Optional[str],
        page_size: int = 100,
    ) -> CRMIncrementalResult:
        payload: Dict[str, Any] = {
            "limit": page_size,
            "properties": [
                "email",
                "phone",
                "firstname",
                "lastname",
                "lastmodifieddate",
            ],
            "sorts": [
                {"propertyName": "lastmodifieddate", "direction": "ASCENDING"}
            ],
        }

        if since:
            payload["filterGroups"] = [
                {
                    "filters": [
                        {
                            "propertyName": "lastmodifieddate",
                            "operator": "GTE",
                            "value": int(since.timestamp() * 1000),
                        }
                    ]
                }
            ]

        if cursor:
            payload["after"] = cursor

        endpoint = f"{self.base_url}/crm/v3/objects/contacts/search"

        with httpx.Client(timeout=self._http_timeout) as client:
            response = client.post(endpoint, headers=self._auth_header, json=payload)

        if response.status_code >= 400:
            raise ProviderSyncError(self.slug, f"Polling falhou: {response.text}")

        body = response.json()
        results = body.get("results", [])
        changes: List[CRMContactChange] = []
        for item in results:
            contact_id = str(item.get("id"))
            changed_at = _parse_timestamp(
                item.get("properties", {}).get("lastmodifieddate")
                or item.get("updatedAt")
            )
            changes.append(
                CRMContactChange(
                    external_id=contact_id,
                    changed_at=changed_at,
                    data=item,
                    change_type="upsert",
                    origin="polling",
                    change_id=str(item.get("id")),
                    raw_payload=item,
                )
            )

        paging = body.get("paging", {})
        next_cursor = None
        if "next" in paging and isinstance(paging["next"], dict):
            next_cursor = paging["next"].get("after")

        has_more = bool(next_cursor)
        return CRMIncrementalResult(
            changes=changes,
            next_cursor=next_cursor,
            has_more=has_more,
            raw_response=body,
        )
