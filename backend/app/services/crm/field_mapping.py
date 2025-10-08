"""Ferramentas para mapeamento de campos customizados em integrações CRM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .exceptions import FieldMappingError


@dataclass(frozen=True)
class FieldMappingConfig:
    """Configuração de mapeamento de campos."""

    core_fields: Mapping[str, str]
    custom_attributes: Mapping[str, str]


class CRMFieldMapper:
    """Aplica configurações de mapeamento sobre payloads de contato."""

    def __init__(self, config: FieldMappingConfig):
        self.config = config

    def map_contact(self, payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Retorna (dados_principais, atributos_customizados)."""

        core_data: Dict[str, Any] = {}
        for field, path in self.config.core_fields.items():
            value = self._extract_value(payload, path)
            if value is not None:
                core_data[field] = value

        custom_attrs: Dict[str, Any] = {}
        for attr, path in self.config.custom_attributes.items():
            value = self._extract_value(payload, path)
            if value is not None:
                custom_attrs[attr] = value

        return core_data, custom_attrs

    def _extract_value(self, payload: Dict[str, Any], path: str) -> Any:
        """Extrai valores aninhados usando caminhos dot-notation."""

        if not path:
            raise FieldMappingError("Path de mapeamento não pode ser vazio.")

        parts = path.split(".")
        value: Optional[Any] = payload
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value
