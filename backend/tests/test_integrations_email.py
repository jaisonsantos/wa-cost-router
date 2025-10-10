import base64
import hashlib
import hmac
import json
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


from app.api.integrations_email import MASK_TOKEN  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactConsentAudit,
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


def _seed_email_provider(
    db_session,
    *,
    token: str = "verify-token",
    signing_secret: str = "signing-secret",
):
    org = Organization(id=uuid.uuid4(), name="Email Org")
    db_session.add(org)
    db_session.flush()

    provider = Provider(
        org_id=org.id,
        name="SendGrid",
        type="email",
        status="active",
    )
    db_session.add(provider)
    db_session.flush()

    credential = ProviderCredential(
        org_id=org.id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials(
            {
                "inbound_verify_token": token,
                "inbound_signing_secret": signing_secret,
            }
        ),
        is_active=True,
    )
    db_session.add(credential)
    db_session.commit()

    return org, provider, credential


def _build_signature(secret: str, payload: dict) -> str:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_email_webhook_verification_success(client, db_session):
    _seed_email_provider(db_session)

    response = client.get(
        "/integrations/email/webhook",
        params={"token": "verify-token", "challenge": "abc123"},
    )

    assert response.status_code == 200
    assert response.text == "abc123"


def test_email_webhook_verification_fails_with_unknown_token(client, db_session):
    _seed_email_provider(db_session)

    response = client.get(
        "/integrations/email/webhook",
        params={"token": "invalid", "challenge": "nope"},
    )

    assert response.status_code == 403


def test_email_webhook_ingests_message_and_creates_contact(client, db_session):
    org, _, _ = _seed_email_provider(db_session)

    payload = {
        "message_id": "email-123",
        "timestamp": "2025-01-15T12:34:56Z",
        "from": "Ada Lovelace <Ada@example.com>",
        "subject": "Ajuda com pedido #12345",
        "text": "Preciso de suporte urgente.",
    }

    signature = _build_signature("signing-secret", payload)

    response = client.post(
        "/integrations/email/webhook",
        params={"token": "verify-token"},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Email-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    contact = db_session.query(Contact).filter_by(email="ada@example.com").one()
    assert contact.org_id == org.id
    assert contact.full_name == "Ada Lovelace"

    event = db_session.query(MessageEvent).filter_by(provider_event_id="email-123").one()
    assert event.channel == "email"
    assert event.org_id == org.id
    assert event.contact_id == contact.id
    assert event.channel_address == "ada@example.com"
    assert event.attributes["payload"]["subject"] == MASK_TOKEN
    assert event.attributes["subject_digest"] == hashlib.sha256(
        payload["subject"].strip().encode("utf-8")
    ).hexdigest()
    assert event.attributes["text_digest"] == hashlib.sha256(
        payload["text"].strip().encode("utf-8")
    ).hexdigest()

    audit = db_session.query(ContactConsentAudit).filter_by(contact_id=contact.id).one()
    assert audit.org_id == org.id
    assert audit.channel == "email"
    assert audit.status == OptInStatusEnum.granted


def test_email_webhook_rejects_missing_signature(client, db_session):
    _seed_email_provider(db_session)

    payload = {"message_id": "no-signature", "from": "user@example.com"}

    response = client.post(
        "/integrations/email/webhook",
        params={"token": "verify-token"},
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 403


def test_email_webhook_ignores_duplicates(client, db_session):
    _seed_email_provider(db_session)

    payload = {
        "message_id": "dup-1",
        "from": "user@example.com",
        "subject": "Primeira",
        "text": "Mensagem",
    }

    signature = _build_signature("signing-secret", payload)

    first = client.post(
        "/integrations/email/webhook",
        params={"token": "verify-token"},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Email-Signature": signature,
        },
    )
    assert first.status_code == 200
    assert first.json()["processed"] == 1

    second = client.post(
        "/integrations/email/webhook",
        params={"token": "verify-token"},
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Email-Signature": signature,
        },
    )

    assert second.status_code == 200
    assert second.json() == {"status": "ignored", "processed": 0}
