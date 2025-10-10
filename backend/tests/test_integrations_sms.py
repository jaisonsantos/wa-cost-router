import base64
import hashlib
import hmac
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


from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactOptInRequest,
    ContactStatusEnum,
    MessageEvent,
    OptInStatusEnum,
    Organization,
    Provider,
    ProviderCredential,
)

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def build_twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    payload = url
    for key in sorted(params.keys()):
        payload += key + params[key]
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


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


def _seed_provider(db_session, *, number: str = "+15558675309", auth_token: str = "secret"):
    org = Organization(id=uuid.uuid4(), name="SMS Org")
    db_session.add(org)
    db_session.flush()

    provider = Provider(
        org_id=org.id,
        name="Twilio",
        type="sms",
        status="active",
        meta={
            "channels": {"sms": {"inbound_numbers": [number]}},
        },
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org.id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials(
            {
                "account_sid": "AC123",
                "auth_token": auth_token,
                "from_number": number,
            }
        ),
        is_active=True,
    )
    db_session.add(credential)
    db_session.commit()

    return org, provider, credential


def test_sms_webhook_persists_event_with_valid_signature(client, db_session):
    org, provider, _ = _seed_provider(db_session)

    contact = Contact(
        org_id=org.id,
        phone="+15551234567",
        email="contact@example.com",
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.flush()

    opt_in = ContactChannelOptIn(
        org_id=org.id,
        contact_id=contact.id,
        channel="sms",
        channel_address=contact.phone,
        status=OptInStatusEnum.granted,
    )
    db_session.add(opt_in)
    db_session.commit()

    payload = {
        "To": provider.meta["channels"]["sms"]["inbound_numbers"][0],
        "From": contact.phone,
        "Body": "Hello from contact",
        "MessageSid": "SM123",
        "SmsStatus": "received",
        "Timestamp": "2024-10-02T15:04:05Z",
    }

    signature = build_twilio_signature(
        "http://testserver/integrations/sms/webhook", payload, "secret"
    )

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    event = db_session.query(MessageEvent).filter_by(provider_event_id="SM123").one()
    assert event.channel == "sms"
    assert event.contact_id == contact.id
    assert event.delivery_status == "received"
    assert event.attributes["payload"]["Body"] == "***redacted***"
    assert event.attributes["body_digest"] == hashlib.sha256(payload["Body"].encode("utf-8")).hexdigest()


def test_sms_webhook_denies_without_consent_and_enqueues_opt_in(client, db_session):
    org, provider, _ = _seed_provider(db_session)

    contact = Contact(
        org_id=org.id,
        phone="+15559876543",
        email="nooptin@example.com",
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.commit()

    payload = {
        "To": provider.meta["channels"]["sms"]["inbound_numbers"][0],
        "From": contact.phone,
        "Body": "Need opt in",
        "MessageSid": "SM999",
        "SmsStatus": "received",
        "Timestamp": "2024-11-01T10:00:00Z",
    }

    signature = build_twilio_signature(
        "http://testserver/integrations/sms/webhook", payload, "secret"
    )

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "denied"}

    assert db_session.query(MessageEvent).filter_by(provider_event_id="SM999").first() is None

    opt_in_request = db_session.query(ContactOptInRequest).filter_by(contact_id=contact.id).one()
    assert opt_in_request.requested_channel == "sms"
    assert opt_in_request.requested_address == contact.phone


def test_sms_webhook_invalid_signature_returns_403(client, db_session):
    org, provider, _ = _seed_provider(db_session)

    contact = Contact(
        org_id=org.id,
        phone="+15550101010",
        email="valid@example.com",
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.flush()

    opt_in = ContactChannelOptIn(
        org_id=org.id,
        contact_id=contact.id,
        channel="sms",
        channel_address=contact.phone,
        status=OptInStatusEnum.granted,
    )
    db_session.add(opt_in)
    db_session.commit()

    payload = {
        "To": provider.meta["channels"]["sms"]["inbound_numbers"][0],
        "From": contact.phone,
        "Body": "Tampered",
        "MessageSid": "SM321",
        "SmsStatus": "received",
        "Timestamp": "2024-09-15T08:30:00Z",
    }

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": "invalid"},
    )

    assert response.status_code == 403
    assert db_session.query(MessageEvent).filter_by(provider_event_id="SM321").first() is None


def test_sms_webhook_returns_ignored_for_unknown_destination(client, db_session):
    _seed_provider(db_session)

    payload = {
        "To": "+15551230000",
        "From": "+15557654321",
        "Body": "Unknown dest",
        "MessageSid": "SM404",
        "SmsStatus": "received",
        "Timestamp": "2024-12-01T01:00:00Z",
    }

    signature = build_twilio_signature(
        "http://testserver/integrations/sms/webhook", payload, "secret"
    )

    response = client.post(
        "/integrations/sms/webhook",
        data=payload,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert (
        db_session.query(MessageEvent)
        .filter_by(provider_event_id="SM404")
        .first()
        is None
    )
