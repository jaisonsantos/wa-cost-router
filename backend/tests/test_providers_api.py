from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Dict

import pytest
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


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):  # pragma: no cover - compile hook
    return "CHAR(36)"


from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Organization, Provider, ProviderCredential  # noqa: E402


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


@pytest.fixture
def auth_context(db_session):
    org = Organization(id=uuid.uuid4(), name="Providers Org")
    db_session.add(org)
    db_session.commit()

    def override_user():
        return {"user_id": uuid.uuid4(), "org_id": org.id}

    app.dependency_overrides[get_current_user] = override_user
    try:
        yield org
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _seed_provider(
    db_session,
    *,
    org_id: uuid.UUID,
    name: str,
    provider_type: str,
    metadata: Dict[str, object],
    credentials: Dict[str, str],
):
    provider = Provider(
        org_id=org_id,
        name=name,
        type=provider_type,
        status="active",
        meta=metadata,
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org_id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials(credentials),
        is_active=True,
    )
    db_session.add(credential)
    db_session.commit()

    return provider


def test_list_providers_includes_form_schema(client, db_session, auth_context):
    org = auth_context

    sms_meta = {
        "channels": {"sms": {"inbound_numbers": ["+15558675309"], "sandbox": True}},
        "provider": "twilio",
    }
    email_meta = {
        "channels": {"email": {"from_address": "noreply@example.com", "sandbox": True}},
        "provider": "sendgrid",
    }

    twilio = _seed_provider(
        db_session,
        org_id=org.id,
        name="Twilio Sandbox",
        provider_type="sms",
        metadata=sms_meta,
        credentials={
            "account_sid": "AC" + "1" * 32,
            "auth_token": "A" * 32,
            "from_number": "+15558675309",
        },
    )

    sendgrid = _seed_provider(
        db_session,
        org_id=org.id,
        name="SendGrid Sandbox",
        provider_type="email",
        metadata=email_meta,
        credentials={
            "api_key": "SG." + "a" * 24,
            "from_email": "noreply@example.com",
            "webhook_token": "sandbox-token",
            "inbound_signing_secret": "B" * 32,
        },
    )

    response = client.get("/providers")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)

    sms_entry = next(item for item in payload if item["id"] == str(twilio.id))
    assert sms_entry["metadata"]["channels"]["sms"]["inbound_numbers"] == ["+15558675309"]
    assert "account_sid" in sms_entry["required_fields"]
    sms_fields = {field["key"] for field in sms_entry["provider_form_schema"]["fields"]}
    assert {"account_sid", "auth_token", "from_number"}.issubset(sms_fields)

    email_entry = next(item for item in payload if item["id"] == str(sendgrid.id))
    assert "api_key" in email_entry["required_fields"]
    assert any(
        field["key"] == "inbound_signing_secret"
        for field in email_entry["provider_form_schema"]["fields"]
    )


def test_set_credentials_requires_required_fields(client, db_session, auth_context):
    org = auth_context

    provider = _seed_provider(
        db_session,
        org_id=org.id,
        name="Twilio Sandbox",
        provider_type="sms",
        metadata={"provider": "twilio"},
        credentials={
            "account_sid": "AC" + "1" * 32,
            "auth_token": "A" * 32,
            "from_number": "+15558675309",
        },
    )

    response = client.post(
        "/providers/credentials",
        json={
            "provider_id": str(provider.id),
            "credentials": {"account_sid": "AC" + "2" * 32},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert "errors" in payload["detail"]
    assert any("Auth Token" in message for message in payload["detail"]["errors"])


def test_provider_health_without_credentials_returns_payload(client, db_session, auth_context):
    org = auth_context

    provider = Provider(
        org_id=org.id,
        name="Twilio Sandbox",
        type="sms",
        status="active",
        meta={"provider": "twilio"},
    )
    db_session.add(provider)
    db_session.commit()

    response = client.post(f"/providers/{provider.id}/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["provider_id"] == str(provider.id)
    assert payload["healthy"] is False
    assert payload["error"] == "No credentials configured"


def test_connection_test_without_credentials_returns_error(client, db_session, auth_context):
    org = auth_context

    provider = Provider(
        org_id=org.id,
        name="SendGrid",
        type="email",
        status="active",
        meta={"provider": "sendgrid"},
    )
    db_session.add(provider)
    db_session.commit()

    response = client.post(
        "/integrations/email/test",
        json={"provider_id": str(provider.id)},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["metadata"]["provider_id"] == str(provider.id)
    assert payload["healthy"] is False
    assert payload["status"] == "error"
    assert payload["error"] == "Provider credentials not configured"

