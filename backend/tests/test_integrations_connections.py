import sys
import uuid
from pathlib import Path

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
from app.core.security import encrypt_credentials, encrypt_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    IntegrationHealthStatus,
    Organization,
    Provider,
    ProviderCredential,
    WAConnection,
)


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
    organization = Organization(id=uuid.uuid4(), name="Connections Org")
    db_session.add(organization)
    db_session.commit()

    def override_user():
        return {"user_id": uuid.uuid4(), "org_id": organization.id}

    app.dependency_overrides[get_current_user] = override_user
    try:
        yield organization
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_list_connections_includes_health_snapshots(client, db_session, auth_context):
    org = auth_context

    wa_connection = WAConnection(
        org_id=org.id,
        business_id="biz-123",
        phone_id="phone-456",
        access_token_enc=encrypt_token("token-abc"),
        webhook_verify_token="verify-token",
        webhook_secret_enc=encrypt_token("secret-xyz"),
        status="active",
    )
    db_session.add(wa_connection)
    db_session.flush()

    provider = Provider(
        org_id=org.id,
        name="SendGrid",
        type="email",
        status="active",
        base_url="https://api.sendgrid.com/v3",
        meta={"display_name": "Email (SendGrid)"},
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org.id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials({"api_key": "fake"}),
        is_active=True,
    )
    db_session.add(credential)
    db_session.flush()

    wa_health = IntegrationHealthStatus(
        org_id=org.id,
        channel="whatsapp",
        target_type="wa_connection",
        target_id=wa_connection.id,
        status="healthy",
        healthy=True,
        status_code="200",
        latency_ms=42,
        details={"status": "active"},
    )
    email_health = IntegrationHealthStatus(
        org_id=org.id,
        channel="email",
        target_type="provider",
        target_id=provider.id,
        status="error",
        healthy=False,
        status_code="503",
        error="Timeout",
    )
    db_session.add_all([wa_health, email_health])
    db_session.commit()

    response = client.get("/integrations/connections")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)

    whatsapp_entry = next(item for item in payload if item["channel"] == "whatsapp")
    assert whatsapp_entry["connected"] is True
    assert whatsapp_entry["status"] == "healthy"
    assert whatsapp_entry["metadata"]["business_id"] == "biz-123"
    assert whatsapp_entry["last_health_check"]["healthy"] is True

    email_entry = next(item for item in payload if item["channel"] == "email")
    assert email_entry["has_credentials"] is True
    assert email_entry["status"] == "error"
    assert email_entry["last_health_check"]["error"] == "Timeout"

    sms_entry = next(item for item in payload if item["channel"] == "sms")
    assert sms_entry["connected"] is False
    assert sms_entry["status"] == "disconnected"

    telegram_entry = next(item for item in payload if item["channel"] == "telegram")
    assert telegram_entry["connected"] is False
    assert telegram_entry["status"] == "disconnected"


def test_test_connection_uses_whatsapp_credentials(client, db_session, auth_context):
    org = auth_context

    connection = WAConnection(
        org_id=org.id,
        business_id="biz-verify",
        phone_id="phone-verify",
        access_token_enc=encrypt_token("token-verify"),
        webhook_verify_token="verify-token",
        webhook_secret_enc=encrypt_token("secret-verify"),
        status="active",
    )
    db_session.add(connection)
    db_session.commit()

    response = client.post("/integrations/whatsapp/test")
    assert response.status_code == 200

    data = response.json()
    assert data["healthy"] is True
    assert data["channel"] == "whatsapp"
    assert data["metadata"]["business_id"] == "biz-verify"

    snapshot = db_session.query(IntegrationHealthStatus).filter_by(target_id=connection.id).one()
    assert snapshot.status == "healthy"


def test_test_connection_provider_handles_connector_failure(client, db_session, auth_context, monkeypatch):
    org = auth_context

    provider = Provider(
        org_id=org.id,
        name="Twilio",
        type="sms",
        status="active",
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org.id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials({"account_sid": "AC123", "auth_token": "secret"}),
        is_active=True,
    )
    db_session.add(credential)
    db_session.commit()

    class FailingConnector:
        async def health_check(self):
            return {"healthy": False, "error": "boom", "status_code": 500}

    monkeypatch.setattr(
        "app.services.provider_connectors.get_connector",
        lambda *args, **kwargs: FailingConnector(),
    )

    response = client.post(f"/integrations/sms/test", json={"provider_id": str(provider.id)})
    assert response.status_code == 200

    payload = response.json()
    assert payload["healthy"] is False
    assert payload["error"] == "boom"

    snapshot = db_session.query(IntegrationHealthStatus).filter_by(target_id=provider.id).one()
    assert snapshot.status == "error"
    assert snapshot.error == "boom"
