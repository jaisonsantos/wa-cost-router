"""Tipos básicos e contratos para provedores de CRM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class CRMContactChange:
    """Representa uma alteração incremental recebida de um CRM."""

    external_id: str
    changed_at: datetime
    data: Dict[str, Any]
    change_type: str = "upsert"
    origin: str = "polling"
    change_id: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class CRMIncrementalResult:
    """Resultado de uma chamada incremental."""

    changes: List[CRMContactChange]
    next_cursor: Optional[str]
    has_more: bool
    raw_response: Optional[Dict[str, Any]] = None


class CRMProvider(ABC):
    """Contrato base para provedores CRM."""

    slug: str
    display_name: str
    supports_webhooks: bool = True
    default_field_mapping: Dict[str, str] = {
        "external_id": "id",
        "email": "properties.email",
        "phone": "properties.phone",
        "full_name": "properties.fullName",
        "first_name": "properties.firstname",
        "last_name": "properties.lastname",
    }

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials

    @abstractmethod
    def configure_webhook(self, callback_url: str, secret: str) -> None:
        """Garante que o webhook esteja configurado no provedor."""

    @abstractmethod
    def parse_outbound_webhook(self, payload: Dict[str, Any]) -> List[CRMContactChange]:
        """Converte payloads de webhook em alterações normalizadas."""

    @abstractmethod
    def fetch_incremental_changes(
        self,
        *,
        since: Optional[datetime],
        cursor: Optional[str],
        page_size: int = 100,
    ) -> CRMIncrementalResult:
        """Obtém alterações incrementais por polling."""
