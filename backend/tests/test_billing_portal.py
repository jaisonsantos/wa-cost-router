import sys
import uuid
from types import SimpleNamespace

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Organization, User, BillingSubscription

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


@pytest.fixture(scope="session", autouse=True)
def create_database():
    # Create all tables from Base metadata
    from app.core.database import Base

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
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    def override_current_user():
        return {"user_id": user_id, "org_id": org_id}

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client, org_id, user_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_portal_returns_url(client, db_session, monkeypatch):
    test_client, org_id, user_id = client

    organization = Organization(id=org_id, name="Portal Org")
    user = User(id=user_id, email="owner@example.com", password_hash="x")
    subscription = BillingSubscription(org_id=org_id, stripe_customer_id="cus_test", status="active")
    db_session.add_all([organization, user, subscription])
    db_session.commit()

    class DummyGateway:
        def create_billing_portal_session(self, **kwargs):
            return SimpleNamespace(url="https://stripe.test/portal")

    monkeypatch.setattr("app.api.billing.get_stripe_gateway", lambda: DummyGateway())

    response = test_client.get("/billing/portal")
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"] == "https://stripe.test/portal"


def test_portal_without_customer_returns_400(client, db_session):
    test_client, org_id, user_id = client

    organization = Organization(id=org_id, name="NoCust Org")
    user = User(id=user_id, email="owner@example.com", password_hash="x")
    db_session.add_all([organization, user])
    db_session.commit()

    response = test_client.get("/billing/portal")
    assert response.status_code == 400
