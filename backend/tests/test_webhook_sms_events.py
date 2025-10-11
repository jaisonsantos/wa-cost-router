import base64
import hashlib
import hmac
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

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
from app.models.models import (  # noqa: E402
    ContactOptInRequest,
    MessageEvent,
    OptInRequestStatusEnum,
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


def _build_twilio_signature(url: str, params: Dict[str, str], token: str) -> str:
    payload = url
    for key in sorted(params):
        payload += key + params[key]
    digest = hmac.new(token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def test_sms_webhook_persists_event_and_consent(
    client,
    db_session,
    organization_factory,
    sms_provider_seed,
    contact_factory,
):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id, name="SMS Org")
    seed = sms_provider_seed(org_id=org_id)

    contact = contact_factory(
        org_id=org_id,
        phone="+15551234567",
        opt_ins=[{"channel": "sms"}],
    )

    payload = {
        "To": seed["number"],
        "From": contact.phone,
        "Body": "Hello there",
        "MessageSid": "SM123",
        "SmsStatus": "received",
        "Timestamp": datetime.now(timezone.utc).isoformat(),
    }

    signature = _build_twilio_signature(
        "http://testserver/integrations/sms/webhook",
        payload,
        seed["auth_token"],
    )

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    event = (
        db_session.query(MessageEvent)
        .filter(MessageEvent.provider_event_id == "SM123")
        .one()
    )
    assert event.channel == "sms"
    assert event.contact_id == contact.id
    assert event.attributes["payload"]["Body"] == "***redacted***"


def test_sms_webhook_denies_without_consent(
    client,
    db_session,
    organization_factory,
    sms_provider_seed,
    contact_factory,
):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id, name="SMS Org")
    seed = sms_provider_seed(org_id=org_id)

    contact = contact_factory(
        org_id=org_id,
        phone="+15559876543",
        email="consent@example.com",
        opt_ins=[],
    )

    payload = {
        "To": seed["number"],
        "From": contact.phone,
        "Body": "Need opt in",
        "MessageSid": "SM999",
        "SmsStatus": "received",
        "Timestamp": datetime.now(timezone.utc).isoformat(),
    }

    signature = _build_twilio_signature(
        "http://testserver/integrations/sms/webhook",
        payload,
        seed["auth_token"],
    )

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "denied"}
    assert db_session.query(MessageEvent).count() == 0

    opt_in_request = db_session.query(ContactOptInRequest).first()
    assert opt_in_request is not None
    assert opt_in_request.status == OptInRequestStatusEnum.pending
    assert opt_in_request.requested_channel == "sms"
    assert opt_in_request.requested_address == contact.phone
