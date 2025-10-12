import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.crm.exceptions import ProviderSyncError  # noqa: E402
from app.services.crm.sync import (  # noqa: E402
    CRMIncrementalSyncService,
    CRM_SYNC_FAILURE_COUNTER,
    CRM_SYNC_PROCESSED_COUNTER,
)


class DummyDB:
    def add(self, *_args, **_kwargs):
        pass

    def commit(self):
        pass

    def flush(self):
        pass

    def query(self, *_args, **_kwargs):  # pragma: no cover - not used in tests
        raise NotImplementedError


def _reset_counter(counter, provider_slug: str, origin: str) -> None:
    try:
        counter.remove(provider_slug, origin)
    except KeyError:
        pass


def test_processed_counter_increments(monkeypatch):
    _reset_counter(CRM_SYNC_PROCESSED_COUNTER, "hubspot", "polling")
    _reset_counter(CRM_SYNC_FAILURE_COUNTER, "hubspot", "polling")

    service = CRMIncrementalSyncService(DummyDB(), registry=SimpleNamespace())

    provider_entry = SimpleNamespace(meta={}, id=uuid.uuid4())

    class FakeProvider:
        def __init__(self):
            self.default_field_mapping = {"external_id": "id"}

        def fetch_incremental_changes(self, *, since, cursor, page_size):
            return SimpleNamespace(
                changes=[
                    SimpleNamespace(
                        changed_at=datetime(2024, 5, 1, 12, tzinfo=timezone.utc),
                    )
                ],
                has_more=False,
                next_cursor="cursor-1",
            )

    mapper = SimpleNamespace(map_contact=lambda payload: ({"external_id": "1"}, {}))

    service._resolve_provider = lambda org_id, provider_slug: (provider_entry, FakeProvider())
    service._build_field_mapper = lambda entry, provider: mapper
    service._load_sync_state = lambda entry: {}
    service._apply_changes = lambda **kwargs: 2
    service._determine_last_change = lambda changes: datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    service._update_sync_state = lambda *args, **kwargs: None

    result = service.run_polling_cycle(
        org_id=uuid.uuid4(),
        provider_slug="hubspot",
        since=datetime(2024, 4, 30, 0, 0, tzinfo=timezone.utc),
        page_size=50,
    )

    assert result.processed_contacts == 2
    processed_value = CRM_SYNC_PROCESSED_COUNTER.labels(
        provider_slug="hubspot",
        origin="polling",
    )._value.get()
    assert processed_value == 2
    failure_value = CRM_SYNC_FAILURE_COUNTER.labels(
        provider_slug="hubspot",
        origin="polling",
    )._value.get()
    assert failure_value == 0

    _reset_counter(CRM_SYNC_PROCESSED_COUNTER, "hubspot", "polling")
    _reset_counter(CRM_SYNC_FAILURE_COUNTER, "hubspot", "polling")


def test_failure_counter_increments(monkeypatch):
    _reset_counter(CRM_SYNC_PROCESSED_COUNTER, "hubspot", "polling")
    _reset_counter(CRM_SYNC_FAILURE_COUNTER, "hubspot", "polling")

    service = CRMIncrementalSyncService(DummyDB(), registry=SimpleNamespace())
    provider_entry = SimpleNamespace(meta={}, id=uuid.uuid4())

    class FailingProvider:
        def __init__(self):
            self.default_field_mapping = {"external_id": "id"}

        def fetch_incremental_changes(self, *, since, cursor, page_size):
            raise ProviderSyncError("hubspot", "boom")

    mapper = SimpleNamespace(map_contact=lambda payload: ({"external_id": "1"}, {}))

    service._resolve_provider = lambda org_id, provider_slug: (provider_entry, FailingProvider())
    service._build_field_mapper = lambda entry, provider: mapper
    service._load_sync_state = lambda entry: {}
    service._update_sync_state = lambda *args, **kwargs: None

    with pytest.raises(ProviderSyncError):
        service.run_polling_cycle(
            org_id=uuid.uuid4(),
            provider_slug="hubspot",
            since=datetime(2024, 4, 30, 0, 0, tzinfo=timezone.utc),
            page_size=50,
        )

    failure_value = CRM_SYNC_FAILURE_COUNTER.labels(
        provider_slug="hubspot",
        origin="polling",
    )._value.get()
    assert failure_value == 1
    processed_value = CRM_SYNC_PROCESSED_COUNTER.labels(
        provider_slug="hubspot",
        origin="polling",
    )._value.get()
    assert processed_value == 0

    _reset_counter(CRM_SYNC_PROCESSED_COUNTER, "hubspot", "polling")
    _reset_counter(CRM_SYNC_FAILURE_COUNTER, "hubspot", "polling")
