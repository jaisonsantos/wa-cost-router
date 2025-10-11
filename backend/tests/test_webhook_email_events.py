import base64
import hashlib
import hmac
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import ContactConsentAudit, MessageEvent  # noqa: E402

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


def _build_signature(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_email_webhook_verify_returns_challenge(
    client,
    db_session,
    organization_factory,
    email_provider_seed,
):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id, name="Email Org")
    seed = email_provider_seed(org_id=org_id)

    response = client.get(
        "/integrations/email/webhook",
        params={"token": seed["token"], "challenge": "123"},
    )

    assert response.status_code == 200
    assert response.text == "123"


def test_email_webhook_persists_event_and_audit(
    client,
    db_session,
    organization_factory,
    email_provider_seed,
    contact_factory,
):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id, name="Email Org")
    seed = email_provider_seed(org_id=org_id)

    contact = contact_factory(
        org_id=org_id,
        email="alice@example.com",
        opt_ins=[{"channel": "email"}],
    )

    payload = [
        {
            "message_id": "sg-event-1",
            "from": "Alice <alice@example.com>",
            "subject": "Updates",
            "text": "Hello!",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]
    body = json.dumps(payload).encode("utf-8")
    signature = _build_signature(seed["signing_secret"], body)

    response = client.post(
        "/integrations/email/webhook",
        params={"token": seed["token"]},
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Email-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    event = (
        db_session.query(MessageEvent)
        .filter(MessageEvent.provider_event_id == "sg-event-1")
        .one()
    )
    assert event.channel == "email"
    assert event.contact_id == contact.id
    assert event.attributes["payload"]["subject"] == "***redacted***"

    audit = (
        db_session.query(ContactConsentAudit)
        .filter(ContactConsentAudit.contact_id == contact.id)
        .one()
    )
    assert audit.channel == "email"
    assert audit.status.value == "granted"
    assert audit.context["provider_event_id"] == "sg-event-1"
    assert audit.context["masked_subject"] == "***redacted***"


def test_email_webhook_rejects_invalid_signature(
    client,
    db_session,
    organization_factory,
    email_provider_seed,
):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id)
    seed = email_provider_seed(org_id=org_id)

    response = client.post(
        "/integrations/email/webhook",
        params={"token": seed["token"]},
        data=json.dumps({"message_id": "sg-event-2"}),
        headers={"Content-Type": "application/json", "X-Email-Signature": "invalid"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid signature"
