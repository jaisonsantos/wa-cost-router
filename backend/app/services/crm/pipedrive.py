"""Provedor CRM para Pipedrive."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx

from app.core.config import settings

from .base import CRMContactChange, CRMIncrementalResult, CRMProvider
from .exceptions import ProviderSyncError


def _parse_datetime(raw: Any) -> datetime:
    """Converte diferentes formatos de data/hora do Pipedrive para UTC."""

    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc)

    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return datetime.now(timezone.utc)
        # Formatos suportados: "YYYY-MM-DD HH:MM:SS" ou ISO 8601
        try:
            if "T" in candidate or candidate.endswith("Z"):
                normalized = candidate.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized).astimezone(timezone.utc)
            parsed = datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    return datetime.now(timezone.utc)


def _extract_primary(items: Iterable[Dict[str, Any]]) -> Optional[str]:
    """Retorna o valor primário de uma lista de campos do Pipedrive."""

    for item in items:
        if isinstance(item, dict) and item.get("value"):
            if item.get("primary") in {True, 1, "1", "true", "True"}:
                return str(item["value"]).strip()

    for item in items:
        if isinstance(item, dict) and item.get("value"):
            return str(item["value"]).strip()

    return None


@dataclass
class _Pagination:
    next_cursor: Optional[str]
    has_more: bool


def _normalize_domain(domain: str) -> str:
    """Remove esquema e paths extras do domínio informado."""

    cleaned = domain.strip()
    if cleaned.startswith("http://"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("https://"):
        cleaned = cleaned[8:]

    return cleaned.split("/")[0]


class PipedriveProvider(CRMProvider):
    """Implementação do conector Pipedrive (polling de persons)."""

    slug = "pipedrive"
    display_name = "Pipedrive CRM"
    supports_webhooks = False
    default_field_mapping = {
        "external_id": "id",
        "email": "primary_email",
        "phone": "primary_phone",
        "first_name": "first_name",
        "last_name": "last_name",
        "full_name": "name",
    }

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)

        token = credentials.get("api_token")
        if not token:
            raise ProviderSyncError(self.slug, "Token de API não informado nas credenciais.")
        self._api_token = token

        company_domain = credentials.get("company_domain")
        if not company_domain:
            raise ProviderSyncError(self.slug, "Domínio da empresa (company_domain) não informado.")

        normalized_domain = _normalize_domain(str(company_domain))
        template = credentials.get("base_url_template") or settings.CRM_PIPEDRIVE_BASE_URL_TEMPLATE
        self.base_url = credentials.get("base_url") or template.format(company_domain=normalized_domain)
        self.base_url = self.base_url.rstrip("/")

        self._timeout = float(credentials.get("timeout", 30.0))
        configured_max_page = int(credentials.get("max_page_size", settings.CRM_PIPEDRIVE_MAX_PAGE_SIZE))
        self._max_page_size = max(1, min(configured_max_page, settings.CRM_PIPEDRIVE_MAX_PAGE_SIZE))

    def configure_webhook(self, callback_url: str, secret: str) -> None:  # pragma: no cover - operação não suportada
        raise ProviderSyncError(self.slug, "Webhooks não são suportados na integração beta do Pipedrive.")

    def parse_outbound_webhook(self, payload: Dict[str, Any]) -> List[CRMContactChange]:
        # Pipedrive beta não envia webhooks; retornamos vazio.
        return []

    def fetch_incremental_changes(
        self,
        *,
        since: Optional[datetime],
        cursor: Optional[str],
        page_size: int = 100,
    ) -> CRMIncrementalResult:
        limit = max(1, min(page_size, self._max_page_size))
        params: Dict[str, Any] = {
            "api_token": self._api_token,
            "limit": limit,
            "sort": "update_time ASC",
        }

        if cursor:
            params["start"] = int(cursor)

        since_utc: Optional[datetime] = None
        if since:
            since_utc = since.astimezone(timezone.utc)

        endpoint = f"{self.base_url}/persons"
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(endpoint, params=params)

        if response.status_code >= 400:
            raise ProviderSyncError(self.slug, f"Polling falhou: {response.text}")

        body = response.json()
        if body.get("success") is False:
            raise ProviderSyncError(self.slug, f"Polling retornou falha: {body}")

        data_items = body.get("data") or []
        changes: List[CRMContactChange] = []

        for person in data_items:
            person_id = str(person.get("id")) if person.get("id") is not None else None
            if not person_id:
                continue

            updated_at = _parse_datetime(person.get("update_time") or person.get("add_time"))
            if since_utc and updated_at <= since_utc:
                continue

            normalized_payload = dict(person)
            emails = person.get("email") or []
            phones = person.get("phone") or []
            normalized_payload["primary_email"] = _extract_primary(emails)
            normalized_payload["primary_phone"] = _extract_primary(phones)
            normalized_payload["id"] = person_id

            change_id = f"{person_id}:{int(updated_at.timestamp())}"
            changes.append(
                CRMContactChange(
                    external_id=person_id,
                    changed_at=updated_at,
                    data=normalized_payload,
                    change_type="upsert",
                    origin="polling",
                    change_id=change_id,
                    raw_payload=person,
                )
            )

        pagination = body.get("additional_data", {}).get("pagination", {})
        pagination_info = self._extract_pagination(pagination)

        return CRMIncrementalResult(
            changes=changes,
            next_cursor=pagination_info.next_cursor,
            has_more=pagination_info.has_more,
            raw_response=body,
        )

    def _extract_pagination(self, pagination: Dict[str, Any]) -> _Pagination:
        has_more = bool(pagination.get("more_items_in_collection"))
        next_cursor: Optional[str] = None
        if has_more:
            next_start = pagination.get("next_start")
            if next_start is not None:
                next_cursor = str(next_start)
        return _Pagination(next_cursor=next_cursor, has_more=has_more)
