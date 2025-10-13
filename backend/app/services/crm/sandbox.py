"""Sandbox-friendly CRM providers used during local and CI runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import encrypt_credentials
from app.models.models import Provider, ProviderCredential

from .base import CRMContactChange, CRMIncrementalResult
from .hubspot import HubSpotProvider, _parse_timestamp


class SandboxHubSpotProvider(HubSpotProvider):
    """HubSpot provider that returns deterministic data instead of calling the API."""

    display_name = "HubSpot CRM (Sandbox)"

    def __init__(self, credentials: Dict[str, object]):
        # Ensure the parent constructor receives an access token to avoid validation errors.
        sanitized = dict(credentials or {})
        token = sanitized.get("access_token") or sanitized.get("private_app_token")
        if not token:
            sanitized["access_token"] = "sandbox-access-token"
        super().__init__(sanitized)
        raw_seed = sanitized.get("seed_contacts")
        self._seed_contacts: List[Dict[str, object]] = []
        if isinstance(raw_seed, list):
            self._seed_contacts = [contact for contact in raw_seed if isinstance(contact, dict)]

    # ------------------------------------------------------------------
    def configure_webhook(self, callback_url: str, secret: str) -> None:  # noqa: ARG002 - interface
        """Sandbox provider does not reach out to HubSpot; configuration is a no-op."""

    # ------------------------------------------------------------------
    def fetch_incremental_changes(
        self,
        *,
        since: Optional[datetime],
        cursor: Optional[str],
        page_size: int = 100,
    ) -> CRMIncrementalResult:
        """Return seeded contacts so polling succeeds during CI/newman runs."""

        now = datetime.now(timezone.utc)

        contacts = self._seed_contacts or [
            {
                "id": "hubspot-sandbox-contact",
                "properties": {
                    "firstname": "Taylor",
                    "lastname": "Sandbox",
                    "email": "crm.sandbox@example.com",
                    "phone": "+15550000000",
                    "lastmodifieddate": int(now.timestamp() * 1000),
                },
            }
        ]

        limit = page_size or len(contacts)
        max_items = max(1, min(len(contacts), limit))
        selected_contacts = contacts[:max_items]

        changes: List[CRMContactChange] = []
        for index, contact in enumerate(selected_contacts):
            contact_id = str(contact.get("id") or f"sandbox-{index+1}")
            properties = contact.get("properties") or {}
            last_modified = (
                contact.get("last_change_at")
                or properties.get("lastmodifieddate")
                or now.isoformat()
            )
            changed_at = _parse_timestamp(last_modified)

            payload = {
                "id": contact_id,
                "properties": properties,
                "updatedAt": changed_at.isoformat(),
            }

            changes.append(
                CRMContactChange(
                    external_id=contact_id,
                    changed_at=changed_at,
                    data=payload,
                    change_type="upsert",
                    origin="polling",
                    change_id=str(contact.get("change_id") or contact_id),
                    raw_payload=payload,
                )
            )

        return CRMIncrementalResult(
            changes=changes,
            next_cursor=None,
            has_more=False,
            raw_response={
                "sandbox": True,
                "source": "seed_contacts",
                "count": len(changes),
                "cursor": cursor,
                "since": since.isoformat() if isinstance(since, datetime) else since,
            },
        )


_SANDBOX_PROVIDER_NAME = "HubSpot Sandbox"
_SANDBOX_DEFAULT_CONTACT = {
    "id": "hubspot-sandbox-contact",
    "properties": {
        "firstname": "Taylor",
        "lastname": "Sandbox",
        "email": "crm.sandbox@example.com",
        "phone": "+15550000000",
    },
}


def ensure_sandbox_crm_provider(db: Session, org_id: UUID) -> Provider:
    """Ensure a sandbox CRM provider and credentials exist for the given org."""

    provider = (
        db.query(Provider)
        .filter(Provider.org_id == org_id, Provider.type == "crm", Provider.name == _SANDBOX_PROVIDER_NAME)
        .one_or_none()
    )

    meta = {"slug": SandboxHubSpotProvider.slug}
    if provider is None:
        provider = Provider(
            org_id=org_id,
            name=_SANDBOX_PROVIDER_NAME,
            type="crm",
            status="active",
            meta=meta,
        )
        db.add(provider)
        db.flush()
    else:
        merged_meta = dict(provider.meta or {})
        merged_meta.update(meta)
        provider.status = "active"
        provider.meta = merged_meta

    credentials_payload: Dict[str, object] = {
        "access_token": "sandbox-crm-access-token",
        "seed_contacts": [
            {
                **_SANDBOX_DEFAULT_CONTACT,
                "properties": {
                    **_SANDBOX_DEFAULT_CONTACT["properties"],
                    "lastmodifieddate": int(datetime.now(timezone.utc).timestamp() * 1000),
                },
            }
        ],
    }

    credential = (
        db.query(ProviderCredential)
        .filter(
            ProviderCredential.org_id == org_id,
            ProviderCredential.provider_id == provider.id,
        )
        .one_or_none()
    )

    encrypted = encrypt_credentials(credentials_payload)
    if credential is None:
        credential = ProviderCredential(
            org_id=org_id,
            provider_id=provider.id,
            credentials_encrypted=encrypted,
            is_active=True,
        )
        db.add(credential)
    else:
        credential.credentials_encrypted = encrypted
        credential.is_active = True

    db.flush()
    return provider

