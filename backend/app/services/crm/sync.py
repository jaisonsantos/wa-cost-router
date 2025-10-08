"""Serviço para sincronização incremental com CRMs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Contact, ContactStatusEnum, Provider

from .base import CRMContactChange, CRMProvider
from .credentials import CRMCredentialStore
from .exceptions import ProviderNotConfiguredError, ProviderSyncError
from .field_mapping import CRMFieldMapper, FieldMappingConfig
from .registry import CRMProviderRegistry


@dataclass(slots=True)
class SyncResult:
    """Resumo padronizado após processar alterações CRM."""

    processed_contacts: int
    has_more: bool
    next_cursor: Optional[str]
    last_change_at: Optional[datetime]
    origin: str


class CRMIncrementalSyncService:
    """Coordena sincronização incremental via webhooks e polling."""

    def __init__(
        self,
        db: Session,
        *,
        registry: CRMProviderRegistry,
        credential_store: Optional[CRMCredentialStore] = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.credential_store = credential_store or CRMCredentialStore(db)

    # ------------------------------------------------------------------
    def handle_webhook_event(
        self,
        *,
        org_id,
        provider_slug: str,
        payload: Dict[str, Any],
    ) -> SyncResult:
        provider_entry, provider_instance = self._resolve_provider(org_id, provider_slug)
        mapper = self._build_field_mapper(provider_entry, provider_instance)
        changes = provider_instance.parse_outbound_webhook(payload)
        last_change = self._determine_last_change(changes)
        processed = self._apply_changes(
            org_id=org_id,
            provider_slug=provider_slug,
            mapper=mapper,
            changes=changes,
        )

        self._update_sync_state(
            provider_entry,
            origin="webhook",
            last_change_at=last_change,
            cursor=None,
        )

        return SyncResult(
            processed_contacts=processed,
            has_more=False,
            next_cursor=None,
            last_change_at=last_change,
            origin="webhook",
        )

    def run_polling_cycle(
        self,
        *,
        org_id,
        provider_slug: str,
        since: Optional[datetime] = None,
        page_size: Optional[int] = None,
    ) -> SyncResult:
        provider_entry, provider_instance = self._resolve_provider(org_id, provider_slug)
        mapper = self._build_field_mapper(provider_entry, provider_instance)

        state = self._load_sync_state(provider_entry)
        cursor = state.get("cursor")
        if since is None:
            since = state.get("last_change_at")

        try:
            result = provider_instance.fetch_incremental_changes(
                since=since,
                cursor=cursor,
                page_size=page_size or settings.CRM_MAX_PAGE_SIZE,
            )
        except ProviderSyncError:
            raise
        except Exception as exc:  # pragma: no cover - defensivo
            raise ProviderSyncError(provider_slug, str(exc)) from exc

        processed = self._apply_changes(
            org_id=org_id,
            provider_slug=provider_slug,
            mapper=mapper,
            changes=result.changes,
        )

        last_change = self._determine_last_change(result.changes) or since
        self._update_sync_state(
            provider_entry,
            origin="polling",
            last_change_at=last_change,
            cursor=result.next_cursor,
        )

        return SyncResult(
            processed_contacts=processed,
            has_more=result.has_more,
            next_cursor=result.next_cursor,
            last_change_at=last_change,
            origin="polling",
        )

    # ------------------------------------------------------------------
    def _resolve_provider(
        self,
        org_id,
        provider_slug: str,
    ) -> tuple[Provider, CRMProvider]:
        provider_entry = self._load_provider(org_id, provider_slug)
        provider_cls = self.registry.get(provider_slug)
        credentials = self.credential_store.get_credentials(
            org_id=org_id,
            provider_id=provider_entry.id,
            provider_slug=provider_slug,
        )
        provider_instance = provider_cls(credentials)
        return provider_entry, provider_instance

    def _load_provider(self, org_id, provider_slug: str) -> Provider:
        candidates: List[Provider] = (
            self.db.query(Provider)
            .filter(
                Provider.org_id == org_id,
                Provider.type == "crm",
            )
            .all()
        )

        for candidate in candidates:
            meta = candidate.meta or {}
            candidate_slug = meta.get("slug") or candidate.name
            if candidate_slug == provider_slug:
                return candidate

        raise ProviderNotConfiguredError(provider_slug)

    def _build_field_mapper(
        self,
        provider_entry: Provider,
        provider: CRMProvider,
    ) -> CRMFieldMapper:
        meta = provider_entry.meta or {}
        mapping_meta = meta.get("field_mapping") or {}
        core_mapping = mapping_meta.get("core") or provider.default_field_mapping
        custom_mapping = mapping_meta.get("custom_attributes") or {}

        if "external_id" not in core_mapping:
            core_mapping = {"external_id": provider.default_field_mapping.get("external_id", "id"), **core_mapping}

        config = FieldMappingConfig(core_fields=core_mapping, custom_attributes=custom_mapping)
        return CRMFieldMapper(config)

    def _load_sync_state(self, provider_entry: Provider) -> Dict[str, Any]:
        meta = provider_entry.meta or {}
        raw_state = meta.get("crm_sync") or {}
        parsed_state: Dict[str, Any] = {}
        if "cursor" in raw_state:
            parsed_state["cursor"] = raw_state.get("cursor")
        if "last_change_at" in raw_state:
            parsed_state["last_change_at"] = self._parse_datetime(raw_state["last_change_at"])
        return parsed_state

    def _update_sync_state(
        self,
        provider_entry: Provider,
        *,
        origin: str,
        last_change_at: Optional[datetime],
        cursor: Optional[str],
    ) -> None:
        meta = dict(provider_entry.meta or {})
        state = dict(meta.get("crm_sync") or {})

        state["last_origin"] = origin
        state["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        if last_change_at:
            state["last_change_at"] = last_change_at.astimezone(timezone.utc).isoformat()
        if cursor is not None:
            state["cursor"] = cursor

        meta["crm_sync"] = state
        provider_entry.meta = meta
        self.db.add(provider_entry)
        self.db.commit()

    def _determine_last_change(self, changes: Iterable[CRMContactChange]) -> Optional[datetime]:
        timestamps = [change.changed_at for change in changes if change.changed_at]
        if not timestamps:
            return None
        return max(timestamps).astimezone(timezone.utc)

    def _apply_changes(
        self,
        *,
        org_id,
        provider_slug: str,
        mapper: CRMFieldMapper,
        changes: Iterable[CRMContactChange],
    ) -> int:
        processed = 0
        for change in changes:
            if change.change_type == "delete":
                processed += self._archive_contact(org_id=org_id, external_id=change.external_id)
                continue

            payload = change.raw_payload or change.data
            core_data, custom_attributes = mapper.map_contact(payload)
            core_data.setdefault("external_id", change.external_id)
            self._upsert_contact(
                org_id=org_id,
                core_data=core_data,
                custom_attributes=custom_attributes,
                provider_slug=provider_slug,
                change=change,
            )
            processed += 1

        if processed:
            self.db.commit()
        return processed

    def _upsert_contact(
        self,
        *,
        org_id,
        core_data: Dict[str, Any],
        custom_attributes: Dict[str, Any],
        provider_slug: str,
        change: CRMContactChange,
    ) -> Contact:
        external_id = core_data.get("external_id")
        if not external_id:
            raise ProviderSyncError(provider_slug, "Alteração recebida sem external_id mapeado.")

        contact = (
            self.db.query(Contact)
            .filter(Contact.org_id == org_id, Contact.external_id == external_id)
            .one_or_none()
        )

        full_name = core_data.get("full_name")
        if not full_name:
            first = core_data.get("first_name")
            last = core_data.get("last_name")
            if first or last:
                full_name = " ".join(part for part in [first, last] if part)

        if contact:
            if full_name:
                contact.full_name = full_name
            for field in ("first_name", "last_name", "email", "phone"):
                if field in core_data and core_data[field] is not None:
                    setattr(contact, field, core_data[field])
            contact.attributes = {
                **(contact.attributes or {}),
                **custom_attributes,
            }
            metadata = dict(contact.source_metadata or {})
            metadata.setdefault("crm", {})
            metadata["crm"].update(
                {
                    "provider": provider_slug,
                    "last_change_id": change.change_id,
                    "last_origin": change.origin,
                }
            )
            contact.source = "crm_sync"
            contact.source_metadata = metadata
            contact.status = contact.status or ContactStatusEnum.active
            contact.updated_at = change.changed_at
        else:
            contact = Contact(
                org_id=org_id,
                external_id=external_id,
                full_name=full_name,
                first_name=core_data.get("first_name"),
                last_name=core_data.get("last_name"),
                email=core_data.get("email"),
                phone=core_data.get("phone"),
                status=ContactStatusEnum.active,
                attributes=custom_attributes,
                source="crm_sync",
                source_metadata={
                    "crm": {
                        "provider": provider_slug,
                        "change_id": change.change_id,
                        "origin": change.origin,
                    }
                },
            )
            self.db.add(contact)
            self.db.flush()

        return contact

    def _archive_contact(self, *, org_id, external_id: str) -> int:
        contact = (
            self.db.query(Contact)
            .filter(Contact.org_id == org_id, Contact.external_id == external_id)
            .one_or_none()
        )
        if not contact:
            return 0
        contact.status = ContactStatusEnum.archived
        self.db.add(contact)
        return 1

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        try:
            normalized = str(value)
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized).astimezone(timezone.utc)
        except ValueError:
            return None
