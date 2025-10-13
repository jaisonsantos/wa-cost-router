"""Registry para provedores CRM."""

from __future__ import annotations

from typing import Dict, Type

from app.core.config import settings

from .base import CRMProvider
from .exceptions import ProviderNotRegisteredError
from .hubspot import HubSpotProvider
from .pipedrive import PipedriveProvider
from .sandbox import SandboxHubSpotProvider


class CRMProviderRegistry:
    """Mantém o registro de provedores CRM disponíveis."""

    def __init__(self):
        self._providers: Dict[str, Type[CRMProvider]] = {}

    def register(self, provider_cls: Type[CRMProvider]) -> None:
        self._providers[provider_cls.slug] = provider_cls

    def get(self, slug: str) -> Type[CRMProvider]:
        try:
            return self._providers[slug]
        except KeyError as exc:
            raise ProviderNotRegisteredError(slug) from exc

    def available(self) -> Dict[str, Type[CRMProvider]]:
        return dict(self._providers)


def build_default_registry() -> CRMProviderRegistry:
    """Retorna um registry com provedores built-in registrados."""

    registry = CRMProviderRegistry()
    registry.register(HubSpotProvider)
    registry.register(PipedriveProvider)
    if settings.SANDBOX_PROVIDERS:
        # Override HubSpot with a deterministic sandbox provider for local/CI runs.
        registry.register(SandboxHubSpotProvider)
    return registry
