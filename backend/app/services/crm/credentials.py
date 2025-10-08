"""Gestão de credenciais criptografadas para provedores CRM."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.models.models import ProviderCredential

from .exceptions import CredentialsNotConfiguredError


class CRMCredentialStore:
    """Recupera e descriptografa credenciais de provedores CRM."""

    def __init__(self, db: Session):
        self.db = db

    def get_credentials(self, *, org_id, provider_id, provider_slug: str) -> Dict[str, Any]:
        """Retorna as credenciais descriptografadas para o provedor informado."""

        credential = (
            self.db.query(ProviderCredential)
            .filter(
                ProviderCredential.org_id == org_id,
                ProviderCredential.provider_id == provider_id,
                ProviderCredential.is_active.is_(True),
            )
            .one_or_none()
        )

        if credential is None:
            raise CredentialsNotConfiguredError(provider_slug)

        return decrypt_credentials(credential.credentials_encrypted)
