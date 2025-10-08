"""Serviços e abstrações para integrações com CRMs externos."""

from .base import CRMContactChange, CRMIncrementalResult, CRMProvider
from .credentials import CRMCredentialStore
from .exceptions import (
    CRMError,
    CredentialsNotConfiguredError,
    FieldMappingError,
    ProviderNotConfiguredError,
    ProviderNotRegisteredError,
)
from .field_mapping import CRMFieldMapper, FieldMappingConfig
from .hubspot import HubSpotProvider
from .registry import CRMProviderRegistry, build_default_registry
from .sync import CRMIncrementalSyncService, SyncResult

__all__ = [
    "CRMContactChange",
    "CRMIncrementalResult",
    "CRMProvider",
    "CRMCredentialStore",
    "CRMError",
    "CredentialsNotConfiguredError",
    "FieldMappingError",
    "ProviderNotConfiguredError",
    "ProviderNotRegisteredError",
    "CRMFieldMapper",
    "FieldMappingConfig",
    "CRMProviderRegistry",
    "build_default_registry",
    "CRMIncrementalSyncService",
    "SyncResult",
    "HubSpotProvider",
]
