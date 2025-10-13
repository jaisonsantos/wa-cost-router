"""Sandbox-friendly CRM providers used during local and CI runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

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

