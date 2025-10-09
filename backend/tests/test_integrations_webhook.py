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

from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import decrypt_token, encrypt_token  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
import app.api.opt_in as opt_in_module  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactConsentAudit,
    ContactOptInRequest,
    ContactStatusEnum,
    MessageEvent,
    OptInRequestStatusEnum,
    OptInStatusEnum,
    Organization,
    WAConnection,
)
from app.services.contacts import OptInRequestService  # noqa: E402

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


def _create_opt_in_request(db_session):
    org = Organization(id=uuid.uuid4(), name="Opt Org")
    db_session.add(org)
    db_session.flush()

    contact = Contact(
        org_id=org.id,
        email="optin@example.com",
        phone="+5511999999000",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    service = OptInRequestService(db_session)
    request = service.enqueue_request(
        org_id=org.id,
        contact_id=contact.id,
        requested_channel="whatsapp",
        requested_address=contact.phone,
    )

    return request, contact


def _create_contact_with_opt_in(
    db_session,
    *,
    org_id,
    phone,
    email="contact@example.com",
    grant_opt_in=True,
):
    contact = Contact(
        id=uuid.uuid4(),
        org_id=org_id,
        email=email,
        phone=phone,
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.flush()

    if grant_opt_in:
        opt_in = ContactChannelOptIn(
            org_id=org_id,
            contact_id=contact.id,
            channel="whatsapp",
            channel_address=phone,
            status=OptInStatusEnum.granted,
        )
        db_session.add(opt_in)

    db_session.commit()
    db_session.refresh(contact)
    return contact


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
    contact = _create_contact_with_opt_in(
        db_session,
        org_id=connection.org_id,
        phone="+5511999999999",
    )

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
                                    "text": {"body": "Olá, quero saber mais"},
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
    assert event.contact_id == contact.id
    assert event.attributes["from"] == "***redacted***"
    assert event.attributes["text"]["body"] == "***redacted***"
    stored_ts = event.timestamp_provider
    if stored_ts.tzinfo is None:
        stored_ts = stored_ts.replace(tzinfo=timezone.utc)
    assert stored_ts == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_webhook_receive_ignores_events_with_invalid_signature(client, db_session):
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

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "processed": 0}


def test_webhook_receive_denies_without_active_consent(client, db_session, monkeypatch):
    connection, secret = _create_connection(db_session, phone_id="phone-denied", secret="another-secret")
    contact = _create_contact_with_opt_in(
        db_session,
        org_id=connection.org_id,
        phone="5511888888888",
        grant_opt_in=False,
    )

    captured_enqueues = []

    def fake_enqueue(self, *args, **kwargs):
        captured_enqueues.append(kwargs)
        return None

    monkeypatch.setattr(
        "app.api.integrations.OptInRequestService.enqueue_request",
        fake_enqueue,
        raising=False,
    )

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-denied"},
                            "messages": [
                                {
                                    "id": "wamid.denied",
                                    "from": "5511888888888",
                                    "timestamp": "1700000003",
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
    assert response.json() == {"status": "denied"}
    assert db_session.query(MessageEvent).count() == 0

    audits = db_session.query(ContactConsentAudit).all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.contact_id == contact.id
    assert audit.status == OptInStatusEnum.revoked
    assert audit.channel_address == "5511888888888"

    assert captured_enqueues
    assert captured_enqueues[0]["contact_id"] == contact.id


def test_opt_in_webhook_confirms_request(client, db_session, monkeypatch):
    request_record, contact = _create_opt_in_request(db_session)
    monkeypatch.setattr(settings, "OPT_IN_WEBHOOK_TOKEN", "unit-token")

    payload = {
        "request_id": str(request_record.id),
        "org_id": str(contact.org_id),
        "status": "confirmed",
        "channel": "whatsapp",
        "channel_address": contact.phone,
        "agent": "email-provider",
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "metadata": {"provider": "email"},
    }

    response = client.post(
        "/opt-in/webhook",
        json=payload,
        headers={"X-Opt-In-Token": "unit-token"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "confirmed"

    refreshed = db_session.get(ContactOptInRequest, request_record.id)
    assert refreshed.status == OptInRequestStatusEnum.confirmed
    assert refreshed.opt_in_id is not None
    opt_in = db_session.get(ContactChannelOptIn, refreshed.opt_in_id)
    assert opt_in is not None
    assert opt_in.status.value == "granted"


def test_opt_in_webhook_rejects_invalid_token(client, db_session, monkeypatch):
    request_record, contact = _create_opt_in_request(db_session)
    monkeypatch.setattr(settings, "OPT_IN_WEBHOOK_TOKEN", "expected-token")

    payload = {
        "request_id": str(request_record.id),
        "org_id": str(contact.org_id),
        "status": "confirmed",
        "channel": "whatsapp",
        "channel_address": contact.phone,
    }

    response = client.post(
        "/opt-in/webhook",
        json=payload,
        headers={"X-Opt-In-Token": "wrong"},
    )

    assert response.status_code == 403
    refreshed = db_session.get(ContactOptInRequest, request_record.id)
    assert refreshed.status == OptInRequestStatusEnum.sent


def test_opt_in_webhook_async_enqueues_job(client, db_session, monkeypatch):
    request_record, contact = _create_opt_in_request(db_session)
    monkeypatch.setattr(settings, "OPT_IN_WEBHOOK_TOKEN", "async-token")

    enqueued = []

    def fake_enqueue(request_id, payload):
        enqueued.append((request_id, payload))

    monkeypatch.setattr(opt_in_module, "enqueue_opt_in_confirmation", fake_enqueue)

    payload = {
        "request_id": str(request_record.id),
        "org_id": str(contact.org_id),
        "status": "confirmed",
        "channel": "whatsapp",
        "channel_address": contact.phone,
    }

    response = client.post(
        "/opt-in/webhook",
        params={"async": "true"},
        json=payload,
        headers={"X-Opt-In-Token": "async-token"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "enqueued"
    assert enqueued
    refreshed = db_session.get(ContactOptInRequest, request_record.id)
    assert refreshed.status == OptInRequestStatusEnum.sent
    assert db_session.query(MessageEvent).count() == 0


def test_webhook_receive_ignores_events_without_signature(client, db_session):
    _create_connection(db_session, phone_id="phone-missing", secret="expected-secret")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-missing"},
                            "messages": [
                                {
                                    "id": "wamid.no-signature",
                                    "from": "5511777777777",
                                    "timestamp": "1700000002",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = client.post(
        "/integrations/wa/webhook",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "processed": 0}
    assert db_session.query(MessageEvent).count() == 0


def test_webhook_receive_succeeds_for_multiple_tenants(client, db_session):
    connection_a, secret_a = _create_connection(
        db_session, phone_id="phone-tenant-a", secret="secret-a"
    )
    contact_a = _create_contact_with_opt_in(
        db_session,
        org_id=connection_a.org_id,
        phone="+5511777777777",
    )

    connection_b, secret_b = _create_connection(
        db_session, phone_id="phone-tenant-b", secret="secret-b"
    )
    contact_b = _create_contact_with_opt_in(
        db_session,
        org_id=connection_b.org_id,
        phone="+5511666666666",
    )

    payload_a = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-tenant-a"},
                            "messages": [
                                {
                                    "id": "wamid.tenant-a",
                                    "from": "5511777777777",
                                    "timestamp": "1700000004",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    raw_body_a = json.dumps(payload_a).encode("utf-8")
    signature_a = hmac.new(secret_a.encode("utf-8"), raw_body_a, hashlib.sha256).hexdigest()

    response_a = client.post(
        "/integrations/wa/webhook",
        data=raw_body_a,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature_a}",
        },
    )

    assert response_a.status_code == 200
    assert response_a.json() == {"status": "ok", "processed": 1}

    payload_b = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-tenant-b"},
                            "messages": [
                                {
                                    "id": "wamid.tenant-b",
                                    "from": "5511666666666",
                                    "timestamp": "1700000005",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    raw_body_b = json.dumps(payload_b).encode("utf-8")
    signature_b = hmac.new(secret_b.encode("utf-8"), raw_body_b, hashlib.sha256).hexdigest()

    response_b = client.post(
        "/integrations/wa/webhook",
        data=raw_body_b,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature_b}",
        },
    )

    assert response_b.status_code == 200
    assert response_b.json() == {"status": "ok", "processed": 1}

    events = db_session.query(MessageEvent).order_by(MessageEvent.provider_event_id).all()
    assert len(events) == 2
    event_a = next(e for e in events if e.provider_event_id == "wamid.tenant-a")
    event_b = next(e for e in events if e.provider_event_id == "wamid.tenant-b")

    assert event_a.org_id == connection_a.org_id
    assert event_a.contact_id == contact_a.id
    assert event_b.org_id == connection_b.org_id
    assert event_b.contact_id == contact_b.id


def test_create_connection_upserts_existing_record(client, db_session):
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Org for Connections")
    db_session.add(org)
    db_session.flush()

    def override_user():
        return {"user_id": uuid.uuid4(), "org_id": org_id}

    app.dependency_overrides[get_current_user] = override_user
    try:
        first_payload = {
            "business_id": "biz-1",
            "phone_id": "phone-abc",
            "access_token": "token-initial",
            "webhook_verify_token": "verify-1",
            "webhook_secret": "secret-initial",
        }

        response = client.post("/integrations/wa/connections", json=first_payload)
        assert response.status_code == 200

        db_session.expire_all()
        connections = db_session.query(WAConnection).filter(WAConnection.org_id == org_id).all()
        assert len(connections) == 1
        connection = connections[0]
        assert connection.business_id == "biz-1"
        assert connection.phone_id == "phone-abc"
        assert connection.webhook_verify_token == "verify-1"
        assert decrypt_token(connection.access_token_enc) == "token-initial"
        assert decrypt_token(connection.webhook_secret_enc) == "secret-initial"

        second_payload = {
            "business_id": "biz-1",
            "phone_id": "phone-abc",
            "access_token": "token-updated",
            "webhook_verify_token": "verify-updated",
            "webhook_secret": "secret-updated",
        }

        response_update = client.post("/integrations/wa/connections", json=second_payload)
        assert response_update.status_code == 200

        db_session.expire_all()
        updated_connections = db_session.query(WAConnection).filter(WAConnection.org_id == org_id).all()
        assert len(updated_connections) == 1
        updated_connection = updated_connections[0]
        assert updated_connection.business_id == "biz-1"
        assert updated_connection.phone_id == "phone-abc"
        assert updated_connection.webhook_verify_token == "verify-updated"
        assert decrypt_token(updated_connection.access_token_enc) == "token-updated"
        assert decrypt_token(updated_connection.webhook_secret_enc) == "secret-updated"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_create_connection_allows_verify_token_reuse_from_other_org(client, db_session):
    other_org = Organization(id=uuid.uuid4(), name="Existing Org")
    db_session.add(other_org)
    db_session.flush()

    conflict_connection = WAConnection(
        org_id=other_org.id,
        business_id="biz-existing",
        phone_id="phone-existing",
        access_token_enc=encrypt_token("existing-token"),
        webhook_verify_token="shared-verify",
        webhook_secret_enc=encrypt_token("existing-secret"),
        status="active",
    )
    db_session.add(conflict_connection)
    db_session.flush()

    new_org_id = uuid.uuid4()
    new_org = Organization(id=new_org_id, name="New Org")
    db_session.add(new_org)
    db_session.flush()

    def override_user():
        return {"user_id": uuid.uuid4(), "org_id": new_org_id}

    app.dependency_overrides[get_current_user] = override_user
    try:
        payload = {
            "business_id": "biz-new",
            "phone_id": "phone-new",
            "access_token": "token-new",
            "webhook_verify_token": "shared-verify",
            "webhook_secret": "secret-new",
        }

        response = client.post("/integrations/wa/connections", json=payload)
        assert response.status_code == 200

        db_session.expire_all()
        count_new_org_connections = (
            db_session.query(WAConnection)
            .filter(WAConnection.org_id == new_org_id)
            .count()
        )
        assert count_new_org_connections == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_create_connection_rejects_conflict_within_same_org(client, db_session):
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Conflict Org")
    db_session.add(org)
    db_session.flush()

    def override_user():
        return {"user_id": uuid.uuid4(), "org_id": org_id}

    app.dependency_overrides[get_current_user] = override_user
    try:
        first_payload = {
            "business_id": "biz-1",
            "phone_id": "phone-a",
            "access_token": "token-a",
            "webhook_verify_token": "shared-token",
            "webhook_secret": "secret-a",
        }
        second_payload = {
            "business_id": "biz-2",
            "phone_id": "phone-b",
            "access_token": "token-b",
            "webhook_verify_token": "shared-token",
            "webhook_secret": "secret-b",
        }

        first_response = client.post("/integrations/wa/connections", json=first_payload)
        assert first_response.status_code == 200

        conflict_response = client.post("/integrations/wa/connections", json=second_payload)
        assert conflict_response.status_code == 400
        assert conflict_response.json()["detail"] == "Webhook verify token already in use"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
