import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import fakeredis
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
from app.core.circuit_breaker import CircuitBreakerStore  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.main import app  # noqa: E402
from app.core.rate_limiter import RateLimiter, get_rate_limiter  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactStatusEnum,
    ContactOptInRequest,
    OptInStatusEnum,
    Organization,
    Provider,
    ProviderCredential,
    OptInRequestStatusEnum,
    RateCard,
    RoutingRule,
    CostRecord,
    MessageJob,
    MessageEvent,
)
from app.services.routing_engine import RoutingEngine  # noqa: E402
import app.services.routing_engine as routing_engine_module  # noqa: E402
import app.api.messages as messages_module  # noqa: E402


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

    fake = fakeredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(fake, key_prefix=f"messages-{org_id}")

    def override_rate_limiter():
        return limiter

    circuit_fake = fakeredis.FakeRedis(decode_responses=True)
    circuit_store = CircuitBreakerStore(
        circuit_fake,
        key_prefix=f"circuit-{org_id}",
        threshold=1,
        cooldown_seconds=5,
    )

    def override_circuit_breaker_store():
        return circuit_store

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rate_limiter] = override_rate_limiter
    monkeypatch.setattr(messages_module, "get_circuit_breaker_store", override_circuit_breaker_store)
    monkeypatch.setattr(routing_engine_module, "get_circuit_breaker_store", override_circuit_breaker_store)

    monkeypatch.setattr(settings, "SANDBOX_PROVIDERS", True)
    monkeypatch.setattr(settings, "SANDBOX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "SANDBOX_FAILURE_RATE", 0.0)

    with TestClient(app) as test_client:
        test_client.circuit_breaker_store = circuit_store  # type: ignore[attr-defined]
        yield test_client, org_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_rate_limiter, None)


DEFAULT_NUMBER = "+5511999999999"


def _bootstrap_routing_stack(db_session, org_id, *, to_number: str = DEFAULT_NUMBER):
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
        actions_json={
            "channel": "whatsapp",
            "primary_provider": str(provider.id),
            "fallback_chain": [],
        },
        priority=10,
    )
    db_session.add(rule)

    contact = Contact(
        org_id=org_id,
        phone=to_number,
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.flush()

    opt_in = ContactChannelOptIn(
        org_id=org_id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address=to_number,
        status=OptInStatusEnum.granted,
        version=1,
        source="import",
    )
    db_session.add(opt_in)

    db_session.commit()

    return provider, contact


def _seed_contact_with_opt_in(
    *,
    contact_factory,
    org_id,
    phone: str | None = None,
    email: str | None = None,
    channel: str,
    channel_address: str,
):
    return contact_factory(
        org_id=org_id,
        phone=phone,
        email=email,
        opt_ins=[{"channel": channel, "channel_address": channel_address}],
    )


def _create_rule_for_channel(
    *,
    routing_rule_factory,
    org_id,
    channel: str,
    providers,
    template_category: str = "MARKETING",
):
    return routing_rule_factory(
        org_id=org_id,
        channel=channel,
        providers=providers,
        template_category=template_category,
    )


def test_send_message_enforces_rate_limit(client, db_session, monkeypatch):
    test_client, org_id = client

    fake = fakeredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(fake, key_prefix="messages-test")

    def override_rate_limiter():
        return limiter

    app.dependency_overrides[get_rate_limiter] = override_rate_limiter
    monkeypatch.setattr(settings, "RATE_LIMIT_MESSAGES_PER_MIN", 2)

    try:
        _bootstrap_routing_stack(db_session, org_id)

        for attempt in range(2):
            response = test_client.post(
                "/messages/send",
                json={
                    "idempotency_key": f"rate-limit-{attempt}",
                    "channel": "whatsapp",
                    "channel_address": DEFAULT_NUMBER,
                    "template_id": "welcome",
                    "template_category": "MARKETING",
                    "variables": {"body_params": ["John"]},
                },
            )
            assert response.status_code == 200
            assert response.headers["X-RateLimit-Remaining"] in {"1", "0"}

        response = test_client.post(
            "/messages/send",
            json={
                "idempotency_key": "rate-limit-final",
                "channel": "whatsapp",
                "channel_address": DEFAULT_NUMBER,
                "template_id": "welcome",
                "template_category": "MARKETING",
                "variables": {"body_params": ["John"]},
            },
        )

        assert response.status_code == 429
        assert response.headers["Retry-After"].isdigit()
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert response.json()["detail"].startswith("Rate limit exceeded")
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


def test_send_message_rejects_invalid_channel_address(client):
    test_client, _ = client

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "invalid-number",
            "channel": "whatsapp",
            "channel_address": "5511999999999",  # missing international prefix
            "template_id": "welcome",
        },
    )

    assert response.status_code == 422
    assert any(
        "phone numbers must include country code" in error.get("msg", "")
        for error in response.json()["detail"]
    )


def test_send_message_rejects_invalid_country_code(client):
    test_client, _ = client

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "invalid-country",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "country_iso": "brazil",
        },
    )

    assert response.status_code == 422
    assert any("country_iso" in error["loc"] for error in response.json()["detail"])


def test_send_message_returns_success(client, db_session):
    test_client, org_id = client
    _, contact = _bootstrap_routing_stack(db_session, org_id)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "test-key",
            "channel": "whatsapp",
            "contact_id": str(contact.id),
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

    job_uuid = uuid.UUID(payload["job_id"])
    job = (
        db_session.query(MessageJob)
        .filter(MessageJob.id == job_uuid)
        .one()
    )
    assert job.channel == "whatsapp"
    assert job.channel_address == DEFAULT_NUMBER
    assert job.contact_id == contact.id

    event = (
        db_session.query(MessageEvent)
        .filter(MessageEvent.message_job_id == job_uuid)
        .one()
    )

    assert event.unit_cost_minor == 85
    assert event.baseline_cost_minor == 85
    assert event.currency == "USD"
    assert event.template_name == "welcome"
    assert event.country_iso == "BR"
    assert event.provider_event_id
    assert event.channel == "whatsapp"
    assert event.channel_address == DEFAULT_NUMBER
    assert event.contact_id == contact.id

    stored_cost = (
        db_session.query(CostRecord)
        .filter(CostRecord.message_job_id == job_uuid)
        .one()
    )
    assert stored_cost.price_eur == 85


def test_send_message_handles_routing_engine_error(client, db_session, monkeypatch):
    test_client, org_id = client
    _bootstrap_routing_stack(db_session, org_id)

    def boom(*args, **kwargs):
        raise RuntimeError("routing exploded")

    monkeypatch.setattr(RoutingEngine, "select_provider", boom)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "boom-key",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Jane"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_final"
    assert payload["message"] == "Routing engine error"
    assert payload["provider_used"] is None
    assert db_session.query(MessageEvent).count() == 0


def test_send_message_handles_delivery_exception(client, db_session, monkeypatch):
    test_client, org_id = client
    _bootstrap_routing_stack(db_session, org_id)

    async def boom(**kwargs):
        raise RuntimeError("delivery exploded")

    monkeypatch.setattr(messages_module, "_attempt_delivery_with_fallback", boom)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "delivery-key",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Ravi"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_final"
    assert payload["message"] == "Delivery orchestration error"
    assert payload["provider_used"] is None


def test_send_message_via_email_channel(
    client,
    db_session,
    organization_factory,
    contact_factory,
    email_provider_seed,
    routing_rule_factory,
):
    test_client, org_id = client
    organization_factory(org_id=org_id)

    seed = email_provider_seed(org_id=org_id)
    _create_rule_for_channel(
        routing_rule_factory=routing_rule_factory,
        org_id=org_id,
        channel="email",
        providers=[seed["provider"]],
    )

    contact = _seed_contact_with_opt_in(
        contact_factory=contact_factory,
        org_id=org_id,
        email="recipient@example.com",
        channel="email",
        channel_address="recipient@example.com",
    )

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "email-success",
            "channel": "email",
            "contact_id": str(contact.id),
            "template_id": "welcome_email",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Alice"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "delivered"
    assert payload["provider_used"] == seed["provider"].name
    assert payload["estimated_cost"] == 75

    job = (
        db_session.query(MessageJob)
        .filter(MessageJob.id == uuid.UUID(payload["job_id"]))
        .one()
    )
    assert job.channel == "email"
    assert job.contact_id == contact.id


def test_send_message_sms_with_fallback(
    client,
    db_session,
    monkeypatch,
    organization_factory,
    contact_factory,
    sms_provider_seed,
    provider_factory,
    routing_rule_factory,
):
    test_client, org_id = client
    organization_factory(org_id=org_id)

    primary_seed = sms_provider_seed(org_id=org_id, unit_cost_minor=220)
    backup_provider = provider_factory(
        org_id=org_id,
        name="Backup Twilio",
        provider_type="sms",
        channel="sms",
        unit_cost_minor=150,
        country_iso="BR",
        meta={"channels": {"sms": {"inbound_numbers": ["+15558670000"]}}},
        credentials={
            "account_sid": "AC999",
            "auth_token": "backup-secret",
            "from_number": "+15558670000",
        },
    )

    _create_rule_for_channel(
        routing_rule_factory=routing_rule_factory,
        org_id=org_id,
        channel="sms",
        providers=[primary_seed["provider"], backup_provider],
    )

    contact = _seed_contact_with_opt_in(
        contact_factory=contact_factory,
        org_id=org_id,
        phone="+15551230000",
        channel="sms",
        channel_address="+15551230000",
    )

    attempts: list[str] = []

    class StubConnector:
        def __init__(self, provider_name: str):
            self.provider_name = provider_name

        async def send_message(self, **kwargs):
            attempts.append(self.provider_name)
            if self.provider_name == primary_seed["provider"].name:
                return {
                    "success": False,
                    "error_code": "500",
                    "error_message": "primary failure",
                }
            return {
                "success": True,
                "provider_message_id": "backup-1",
                "response": {"status": "ok"},
            }

    def fake_get_connector(provider_name, credentials, base_url, **kwargs):
        return StubConnector(provider_name)

    monkeypatch.setattr(messages_module, "get_connector", fake_get_connector)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "sms-fallback",
            "channel": "sms",
            "contact_id": str(contact.id),
            "template_id": "promo",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Promo"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "delivered_with_fallback"
    assert payload["provider_used"] == backup_provider.name
    assert attempts == [primary_seed["provider"].name, backup_provider.name]


def test_send_message_idempotency_with_contact_id(
    client,
    db_session,
    organization_factory,
    contact_factory,
    email_provider_seed,
    routing_rule_factory,
):
    test_client, org_id = client
    organization_factory(org_id=org_id)

    seed = email_provider_seed(org_id=org_id)
    _create_rule_for_channel(
        routing_rule_factory=routing_rule_factory,
        org_id=org_id,
        channel="email",
        providers=[seed["provider"]],
    )

    contact = _seed_contact_with_opt_in(
        contact_factory=contact_factory,
        org_id=org_id,
        email="idem@example.com",
        channel="email",
        channel_address="idem@example.com",
    )

    payload = {
        "idempotency_key": "contact-idem",
        "channel": "email",
        "contact_id": str(contact.id),
        "template_id": "digest",
        "template_category": "MARKETING",
        "variables": {"body_params": ["Daily"]},
    }

    first = test_client.post("/messages/send", json=payload)
    assert first.status_code == 200
    first_job = first.json()["job_id"]

    second = test_client.post("/messages/send", json=payload)
    assert second.status_code == 200
    payload_second = second.json()
    assert payload_second["job_id"] == first_job
    assert payload_second["message"] == "Message already processed (idempotent)"

    assert (
        db_session.query(MessageJob)
        .filter(MessageJob.idempotency_key == payload["idempotency_key"])
        .count()
        == 1
    )
    assert db_session.query(MessageEvent).count() == 1


def test_send_message_handles_job_commit_failure(client, db_session, monkeypatch):
    test_client, org_id = client
    _bootstrap_routing_stack(db_session, org_id)

    original_commit = db_session.commit
    call_state = {"calls": 0}

    def failing_first_commit():
        call_state["calls"] += 1
        if call_state["calls"] == 1:
            raise RuntimeError("job commit exploded")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", failing_first_commit)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "job-commit-failure",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Nia"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_final"
    assert payload["message"] == "Message job persistence error"
    assert payload["provider_used"] is None
    assert db_session.query(MessageEvent).count() == 0


def test_send_message_handles_non_iterable_fallback_chain(client, db_session, monkeypatch):
    test_client, org_id = client
    provider, _ = _bootstrap_routing_stack(db_session, org_id)

    def select_with_invalid_fallback(*args, **kwargs):
        return {
            "provider_id": str(provider.id),
            "fallback_chain": "not-a-list",
            "estimated_cost": 85,
            "rule_id": None,
            "rule_name": "test",
        }

    monkeypatch.setattr(RoutingEngine, "select_provider", select_with_invalid_fallback)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "bad-fallback",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Lia"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"delivered", "delivered_with_fallback"}
    assert payload["provider_used"] == "360dialog"

    job_uuid = uuid.UUID(payload["job_id"])
    events = (
        db_session.query(MessageEvent)
        .filter(MessageEvent.message_job_id == job_uuid)
        .all()
    )
    assert len(events) == 1


def test_send_message_defaults_invalid_estimated_cost(client, db_session, monkeypatch):
    test_client, org_id = client
    provider, _ = _bootstrap_routing_stack(db_session, org_id)

    def select_with_invalid_cost(*args, **kwargs):
        return {
            "provider_id": str(provider.id),
            "fallback_chain": [],
            "estimated_cost": "not-a-number",
            "rule_id": None,
            "rule_name": "test",
        }

    monkeypatch.setattr(RoutingEngine, "select_provider", select_with_invalid_cost)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "bad-cost",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Noah"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimated_cost"] == 0

    job_uuid = uuid.UUID(payload["job_id"])
    stored_costs = db_session.query(CostRecord).filter(CostRecord.message_job_id == job_uuid).all()
    assert len(stored_costs) == 1
    assert stored_costs[0].price_eur == 85

    event = (
        db_session.query(MessageEvent)
        .filter(MessageEvent.message_job_id == job_uuid)
        .one()
    )
    assert event.unit_cost_minor == 85
    assert event.baseline_cost_minor == 85


def test_send_message_rejects_when_contact_opted_out(client, db_session):
    test_client, org_id = client
    _, contact = _bootstrap_routing_stack(db_session, org_id)

    revoked = ContactChannelOptIn(
        org_id=org_id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address=DEFAULT_NUMBER,
        status=OptInStatusEnum.revoked,
        version=2,
        source="manual",
    )
    db_session.add(revoked)
    db_session.commit()

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "revoked-key",
            "channel": "whatsapp",
            "contact_id": str(contact.id),
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Kai"]},
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"] == "Contact has no active opt-in for the requested channel."

    jobs = db_session.query(MessageJob).all()
    assert len(jobs) == 1
    assert jobs[0].status.value == "failed_final"
    assert db_session.query(CostRecord).count() == 0


def test_contact_without_consent_triggers_opt_in_request(client, db_session):
    test_client, org_id = client
    _, contact = _bootstrap_routing_stack(db_session, org_id)

    contact.email = "no-consent@example.com"
    db_session.query(ContactChannelOptIn).delete()
    db_session.commit()

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "no-opt-in",
            "channel": "whatsapp",
            "contact_id": str(contact.id),
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Kai"]},
        },
    )

    assert response.status_code == 403

    requests = (
        db_session.query(ContactOptInRequest)
        .filter(ContactOptInRequest.contact_id == contact.id)
        .all()
    )
    assert len(requests) == 1
    request = requests[0]
    assert request.status == OptInRequestStatusEnum.sent
    assert request.delivery_address == "no-consent@example.com"


def test_send_message_rolls_back_on_commit_error(client, db_session, monkeypatch):
    test_client, org_id = client
    _bootstrap_routing_stack(db_session, org_id)

    original_commit = db_session.commit
    call_state = {"calls": 0, "raised": False}

    def flaky_commit():
        call_state["calls"] += 1
        result = original_commit()
        # Let the first commit (job creation) succeed without raising. Fail on
        # the next commit performed during delivery orchestration, mimicking a
        # transactional error after the flush has been executed.
        if call_state["calls"] == 2 and not call_state["raised"]:
            call_state["raised"] = True
            raise RuntimeError("commit exploded")
        return result

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "flaky-commit",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Zoe"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_final"
    assert payload["message"] == "Delivery orchestration error"


def test_circuit_breaker_opens_and_triggers_fallback(client, db_session, monkeypatch):
    test_client, org_id = client
    breaker_store: CircuitBreakerStore = test_client.circuit_breaker_store  # type: ignore[attr-defined]
    primary, _ = _bootstrap_routing_stack(db_session, org_id)

    fallback = Provider(
        org_id=org_id,
        name="gupshup",
        type="whatsapp",
        status="active",
    )
    db_session.add(fallback)
    db_session.flush()

    fallback_credential = ProviderCredential(
        org_id=org_id,
        provider_id=fallback.id,
        credentials_encrypted=encrypt_credentials({"api_key": "sandbox"}),
    )
    db_session.add(fallback_credential)

    fallback_rate = RateCard(
        provider_id=fallback.id,
        effective_from=datetime.utcnow(),
        source="test",
        country_iso="BR",
        category="MARKETING",
        unit_cost_minor=120,
        currency="USD",
    )
    db_session.add(fallback_rate)

    rule = db_session.query(RoutingRule).filter(RoutingRule.org_id == org_id).first()
    assert rule is not None
    rule.actions_json = {
        "channel": "whatsapp",
        "primary_provider": str(primary.id),
        "fallback_chain": [str(fallback.id)],
    }
    db_session.commit()

    class FailingConnector:
        def __init__(self, name: str, *_: object, **__: object) -> None:
            self.name = name

        async def send_message(self, **_: object) -> dict:
            return {
                "success": False,
                "error_code": "500",
                "error_message": "primary down",
                "latency_ms": 5,
                "response": {},
            }

    class SuccessfulConnector:
        def __init__(self, name: str, *_: object, **__: object) -> None:
            self.name = name

        async def send_message(self, **_: object) -> dict:
            return {
                "success": True,
                "provider_message_id": "fallback-1",
                "latency_ms": 3,
                "response": {},
            }

    def fake_connector(
        provider_name: str,
        credentials: dict,
        base_url: str | None = None,
        **_: object,
    ):
        if provider_name == primary.name:
            return FailingConnector(provider_name, credentials, base_url)
        return SuccessfulConnector(provider_name, credentials, base_url)

    monkeypatch.setattr(messages_module, "get_connector", fake_connector)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "circuit-fallback",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Jane"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "delivered_with_fallback"
    assert payload["provider_used"] == fallback.name

    primary_state = breaker_store.get_state(str(primary.id))
    assert primary_state.state == "open"
    fallback_state = breaker_store.get_state(str(fallback.id))
    assert fallback_state.state == "closed"


def test_circuit_breaker_resets_on_success(client, db_session, monkeypatch):
    test_client, org_id = client
    breaker_store: CircuitBreakerStore = test_client.circuit_breaker_store  # type: ignore[attr-defined]
    provider, _ = _bootstrap_routing_stack(db_session, org_id)

    class SuccessfulConnector:
        def __init__(self, name: str, *_: object, **__: object) -> None:
            self.name = name

        async def send_message(self, **_: object) -> dict:
            return {
                "success": True,
                "provider_message_id": "success-1",
                "latency_ms": 2,
                "response": {},
            }

    monkeypatch.setattr(messages_module, "get_connector", SuccessfulConnector)

    response = test_client.post(
        "/messages/send",
        json={
            "idempotency_key": "circuit-success",
            "channel": "whatsapp",
            "channel_address": DEFAULT_NUMBER,
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Jo"]},
        },
    )

    assert response.status_code == 200
    state = breaker_store.get_state(str(provider.id))
    assert state.state == "closed"
    assert state.failure_count == 0

