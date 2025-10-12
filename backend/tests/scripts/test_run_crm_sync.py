import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_module():
    script_path = BACKEND_DIR / "scripts" / "run_crm_sync.py"
    spec = importlib.util.spec_from_file_location("run_crm_sync", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_main_executes_polling(monkeypatch, capsys):
    module = _load_module()

    org_id = uuid.uuid4()
    session = SimpleNamespace(closed=False)

    def fake_session():
        return session

    def fake_close():
        session.closed = True

    session.close = fake_close

    result = SimpleNamespace(
        processed_contacts=2,
        has_more=False,
        next_cursor="cursor-1",
        last_change_at=datetime(2024, 5, 10, 12, 30, tzinfo=timezone.utc),
        origin="polling",
    )

    class FakeService:
        def __init__(self, db, *, registry):
            assert db is session
            self.registry = registry

        def run_polling_cycle(self, *, org_id, provider_slug, since, page_size):
            assert org_id == org_id_value
            assert provider_slug == "hubspot"
            assert since == datetime(2024, 5, 1, 0, 0, tzinfo=timezone.utc)
            assert page_size == 25
            return result

    org_id_value = uuid.UUID(str(org_id))

    monkeypatch.setattr(module, "SessionLocal", fake_session)
    monkeypatch.setattr(module, "CRMIncrementalSyncService", FakeService)
    monkeypatch.setattr(module, "build_default_registry", lambda: "registry")

    exit_code = module.main(
        [
            "--provider",
            "hubspot",
            "--org-id",
            str(org_id),
            "--since",
            "2024-05-01T00:00:00Z",
            "--page-size",
            "25",
        ]
    )

    assert exit_code == 0
    assert session.closed is True

    captured = capsys.readouterr()
    assert captured.out.strip() == (
        '{"processed_contacts": 2, "has_more": false, "next_cursor": "cursor-1", '
        '"last_change_at": "2024-05-10T12:30:00+00:00", "origin": "polling"}'
    )
    assert captured.err == ""


def test_invalid_since(monkeypatch):
    module = _load_module()

    monkeypatch.setattr(module, "SessionLocal", lambda: None)

    with pytest.raises(SystemExit):
        module.main(["--provider", "hubspot", "--org-id", str(uuid.uuid4()), "--since", "invalid"])
