import hashlib
import hmac
import json
import sys
import uuid
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
def compile_uuid(element, compiler, **kw):  # pragma: no cover - compile hook
    return "CHAR(36)"

from app.core.database import Base, get_db  # noqa: E402
from app.core.security import encrypt_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import MessageEvent, Organization, WAConnection  # noqa: E402

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


def _create_connection(db_session, *, verify_token="verify-token", phone_id="phone-1", secret="meta-secret"):
    org = Organization(id=uuid.uuid4(), name="Demo Org")
    db_session.add(org)
    db_session.flush()

    connection = WAConnection(
        org_id=org.id,
        business_id="biz-123",
        phone_id=phone_id,
        access_token_enc=encrypt_token("access-token"),
        webhook_verify_token=verify_token,
        webhook_secret_enc=encrypt_token(secret),
        status="active",
    )
    db_session.add(connection)
    db_session.flush()

    return connection, secret


def test_webhook_verify_returns_challenge_for_valid_token(client, db_session):
    connection, _ = _create_connection(db_session)

    response = client.get(
        "/integrations/wa/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": connection.webhook_verify_token,
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_verify_returns_403_for_invalid_token(client, db_session):
    _create_connection(db_session)

    response = client.get(
        "/integrations/wa/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "invalid-token",
            "hub.challenge": "ignored",
        },
    )

    assert response.status_code == 403


def test_webhook_receive_persists_events_with_valid_signature(client, db_session):
    connection, secret = _create_connection(db_session, phone_id="phone-meta", secret="super-secret")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-meta"},
                            "messages": [
                                {
                                    "id": "wamid.sample",
                                    "from": "5511999999999",
                                    "timestamp": "1700000000",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/integrations/wa/webhook",
        data=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    events = db_session.query(MessageEvent).all()
    assert len(events) == 1
    event = events[0]
    assert event.org_id == connection.org_id
    assert event.connection_id == connection.id
    assert event.provider_event_id == "wamid.sample"


def test_webhook_receive_returns_403_for_invalid_signature(client, db_session):
    _create_connection(db_session, phone_id="phone-invalid", secret="expected-secret")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-invalid"},
                            "messages": [
                                {
                                    "id": "wamid.invalid",
                                    "from": "5511888888888",
                                    "timestamp": "1700000001",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    raw_body = json.dumps(payload).encode("utf-8")
    bad_signature = hmac.new(b"wrong-secret", raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/integrations/wa/webhook",
        data=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={bad_signature}",
        },
    )

    assert response.status_code == 403
    assert db_session.query(MessageEvent).count() == 0
