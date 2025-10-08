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
    CostRecord,
)
from app.services.routing_engine import RoutingEngine  # noqa: E402
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
            "to_number": "+5511999999999",
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
            "to_number": "+5511999999999",
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
            "to_number": "+5511999999999",
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


def test_send_message_handles_non_iterable_fallback_chain(client, db_session, monkeypatch):
    test_client, org_id = client
    provider = _bootstrap_routing_stack(db_session, org_id)

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
            "to_number": "+5511999999999",
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Lia"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"delivered", "delivered_with_fallback"}
    assert payload["provider_used"] == "360dialog"


def test_send_message_defaults_invalid_estimated_cost(client, db_session, monkeypatch):
    test_client, org_id = client
    provider = _bootstrap_routing_stack(db_session, org_id)

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
            "to_number": "+5511999999999",
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
    assert stored_costs[0].price_eur == 0


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
            "to_number": "+5511999999999",
            "template_id": "welcome",
            "template_category": "MARKETING",
            "variables": {"body_params": ["Zoe"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_final"
    assert payload["message"] == "Delivery orchestration error"

