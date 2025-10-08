import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID as PGUUID

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"

from app.api.dependencies import get_current_user  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Organization,
    Provider,
    ProviderCredential,
    RateCard,
    RoutingRule,
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
def client(db_session, monkeypatch):
    org_id = uuid.uuid4()

    def override_current_user():
        return {"user_id": uuid.uuid4(), "org_id": org_id}

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)
    monkeypatch.setattr(settings, "SANDBOX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "SANDBOX_FAILURE_RATE", 0.0)

    with TestClient(app) as test_client:
        yield test_client, org_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _bootstrap_routing_stack(db_session, org_id):
    organization = Organization(id=org_id, name="Test Org")
    db_session.add(organization)

    provider = Provider(
        org_id=org_id,
        name="360dialog",
        type="whatsapp",
        status="active",
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org_id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials({"access_token": "sandbox"}),
    )
    db_session.add(credential)

    rate = RateCard(
        provider_id=provider.id,
        effective_from=datetime.utcnow(),
        source="test",
        country_iso="BR",
        category="MARKETING",
        unit_cost_minor=85,
        currency="USD",
    )
    db_session.add(rate)

    rule = RoutingRule(
        org_id=org_id,
        name="Route BR Marketing",
        is_enabled=True,
        conditions_json=[
            {"type": "country", "values": ["BR"]},
            {"type": "category", "values": ["MARKETING"]},
        ],
        actions_json={"primary_provider": str(provider.id), "fallback_chain": []},
        priority=10,
    )
    db_session.add(rule)

    db_session.commit()

    return provider


def test_send_message_returns_success(client, db_session):
    test_client, org_id = client
    _bootstrap_routing_stack(db_session, org_id)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "test-key",
            "to_number": "+5511999999999",
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["John"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"delivered", "delivered_with_fallback"}
    assert payload["provider_used"] == "360dialog"
    assert payload["estimated_cost"] == 85
    assert payload["job_id"]

