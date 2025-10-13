import hashlib
import hmac
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import pytest
from types import ModuleType, SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if "stripe" not in sys.modules:
    stripe_module = ModuleType("stripe")
    stripe_module.error = SimpleNamespace(StripeError=Exception)  # type: ignore[attr-defined]
    sys.modules["stripe"] = stripe_module


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):  # pragma: no cover - compile hook
    return "CHAR(36)"


from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Organization, Provider, ProviderCredential, Contact  # noqa: E402
from app.services.crm import SyncResult  # noqa: E402

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="session", autouse=True)
def create_database():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db_session(create_database):
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def crm_secret(monkeypatch):
    monkeypatch.setattr(settings, "CRM_WEBHOOK_SECRET", "test-secret")
    yield


def _seed_crm_provider(
    db_session,
    *,
    slug: str = "hubspot",
    with_credentials: bool = True,
) -> Tuple[Organization, Provider]:
    org = Organization(id=uuid.uuid4(), name="CRM Org")
    db_session.add(org)
    db_session.flush()

    provider = Provider(
        org_id=org.id,
        name=slug,
        type="crm",
        status="active",
        meta={"slug": slug},
    )
    db_session.add(provider)
    db_session.flush()

    if with_credentials:
        credential = ProviderCredential(
            org_id=org.id,
            provider_id=provider.id,
            credentials_encrypted=encrypt_credentials({"access_token": "hubspot-token"}),
            is_active=True,
        )
        db_session.add(credential)

    db_session.commit()
    return org, provider


def _build_signature(secret: str, payload: dict) -> str:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return digest


def test_crm_webhook_rejects_invalid_signature(client, db_session):
    org, _ = _seed_crm_provider(db_session)

    payload = {"events": []}
    response = client.post(
        "/integrations/crm/hubspot/webhook",
        params={"org_id": str(org.id)},
        data=json.dumps(payload),
        headers={"Content-Type": "application/json", "X-HubSpot-Signature": "invalid"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


def test_crm_webhook_processes_changes(client, db_session):
    org, _ = _seed_crm_provider(db_session)

    payload = {
        "events": [
            {
                "objectType": "contact.propertyChange",
                "objectId": "12345",
                "occurredAt": "2024-12-01T10:15:30Z",
                "properties": {
                    "firstname": "Ada",
                    "lastname": "Lovelace",
                    "email": "ada@example.com",
                    "phone": "+44123456789",
                },
                "eventId": "evt-1",
            }
        ]
    }

    signature = _build_signature("test-secret", payload)

    response = client.post(
        "/integrations/crm/hubspot/webhook",
        params={"org_id": str(org.id)},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-HubSpot-Signature": signature,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "processed_contacts": 1,
        "has_more": False,
        "next_cursor": None,
        "last_change_at": "2024-12-01T10:15:30+00:00",
        "origin": "webhook",
    }

    contact = db_session.query(Contact).filter(Contact.org_id == org.id).one()
    assert contact.external_id == "12345"
    assert contact.full_name == "Ada"
    assert contact.email == "ada@example.com"
    assert contact.phone == "+44123456789"
    assert contact.source == "crm_sync"
    metadata = contact.source_metadata or {}
    assert metadata.get("crm", {}).get("provider") == "hubspot"


def test_crm_webhook_returns_conflict_without_credentials(client, db_session):
    org, _ = _seed_crm_provider(db_session, with_credentials=False)

    payload = {"events": []}
    signature = _build_signature("test-secret", payload)

    response = client.post(
        "/integrations/crm/hubspot/webhook",
        params={"org_id": str(org.id)},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-HubSpot-Signature": signature,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Provider credentials not configured"


def test_crm_poll_endpoint_returns_sync_summary(monkeypatch, client, db_session):
    org, _ = _seed_crm_provider(db_session)

    summary = SyncResult(
        processed_contacts=2,
        has_more=True,
        next_cursor="cursor-123",
        last_change_at=datetime(2024, 12, 1, 11, 0, tzinfo=timezone.utc),
        origin="polling",
    )

    captured = {}

    def fake_run(self, *, org_id, provider_slug, since=None, page_size=None):
        captured["org_id"] = org_id
        captured["provider_slug"] = provider_slug
        captured["since"] = since
        captured["page_size"] = page_size
        return summary

    monkeypatch.setattr(
        "app.api.integrations_crm.CRMIncrementalSyncService.run_polling_cycle",
        fake_run,
    )

    response = client.post(
        "/integrations/crm/hubspot/poll",
        params={"org_id": str(org.id)},
        json={"page_size": 25},
    )

    assert response.status_code == 200
    assert response.json() == {
        "processed_contacts": 2,
        "has_more": True,
        "next_cursor": "cursor-123",
        "last_change_at": "2024-12-01T11:00:00+00:00",
        "origin": "polling",
    }
    assert captured == {
        "org_id": org.id,
        "provider_slug": "hubspot",
        "since": None,
        "page_size": 25,
    }


def test_sandbox_mode_auto_provisions_provider(monkeypatch, client, db_session):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)

    org = Organization(id=uuid.uuid4(), name="Sandbox Org")
    db_session.add(org)
    db_session.flush()

    response = client.post(
        "/integrations/crm/hubspot/poll",
        params={"org_id": str(org.id)},
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["processed_contacts"] >= 1
    assert body["origin"] == "polling"

    db_session.expire_all()

    provider = (
        db_session.query(Provider)
        .filter(Provider.org_id == org.id, Provider.type == "crm")
        .one()
    )
    assert provider.meta.get("slug") == "hubspot"

    credential = (
        db_session.query(ProviderCredential)
        .filter(
            ProviderCredential.org_id == org.id,
            ProviderCredential.provider_id == provider.id,
        )
        .one_or_none()
    )
    assert credential is not None
    assert credential.is_active is True

    contacts = db_session.query(Contact).filter(Contact.org_id == org.id).all()
    assert contacts
    assert all(contact.source == "crm_sync" for contact in contacts)


def test_sandbox_mode_webhook_creates_provider(monkeypatch, client, db_session):
    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)

    org = Organization(id=uuid.uuid4(), name="Webhook Org")
    db_session.add(org)
    db_session.flush()

    payload = {
        "events": [
            {
                "objectType": "contact.propertyChange",
                "objectId": "sandbox-1",
                "occurredAt": "2024-12-01T12:00:00Z",
                "properties": {
                    "firstname": "Web",
                    "lastname": "Hook",
                    "email": "webhook@example.com",
                },
                "eventId": "evt-sandbox",
            }
        ]
    }

    signature = _build_signature("test-secret", payload)

    response = client.post(
        "/integrations/crm/hubspot/webhook",
        params={"org_id": str(org.id)},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-HubSpot-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json()["processed_contacts"] == 1

    db_session.expire_all()

    provider = (
        db_session.query(Provider)
        .filter(Provider.org_id == org.id, Provider.type == "crm")
        .one()
    )
    assert provider.meta.get("slug") == "hubspot"

    credential = (
        db_session.query(ProviderCredential)
        .filter(
            ProviderCredential.org_id == org.id,
            ProviderCredential.provider_id == provider.id,
        )
        .one_or_none()
    )
    assert credential is not None
    assert credential.is_active is True

    contact = db_session.query(Contact).filter(Contact.org_id == org.id).one()
    assert contact.external_id == "sandbox-1"
