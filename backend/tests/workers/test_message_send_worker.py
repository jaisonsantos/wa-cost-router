import sys
import uuid
from datetime import datetime
from pathlib import Path

import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.circuit_breaker import CircuitBreakerStore  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.models import (  # noqa: E402
    JobStatusEnum,
    MessageJob,
    Provider,
    ProviderCredential,
    RateCard,
)
import app.services.messages.delivery as delivery_module  # noqa: E402
from app.services.messages.delivery import (  # noqa: E402
    DeliveryContext,
    MESSAGES_SEND_COUNTER,
)
from app.workers import message_send as message_worker  # noqa: E402


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


def _bootstrap_provider(session):
    provider = Provider(
        org_id=uuid.uuid4(),
        name="360dialog",
        type="whatsapp",
        status="active",
    )
    session.add(provider)
    session.flush()

    credential = ProviderCredential(
        org_id=provider.org_id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials({"access_token": "sandbox"}),
    )
    session.add(credential)

    rate = RateCard(
        provider_id=provider.id,
        effective_from=datetime.utcnow(),
        source="test",
        country_iso="BR",
        category="MARKETING",
        unit_cost_minor=85,
        currency="USD",
    )
    session.add(rate)

    session.commit()
    return provider


def test_worker_process_message_success(monkeypatch, db_session):
    provider = _bootstrap_provider(db_session)

    job = MessageJob(
        org_id=provider.org_id,
        idempotency_key="worker-success",
        to_number="+5511999999999",
        channel="whatsapp",
        channel_address="+5511999999999",
        template_id="welcome",
        template_category="MARKETING",
        variables={"body_params": ["Ada"]},
        country_iso="BR",
        status=JobStatusEnum.pending,
    )
    db_session.add(job)
    db_session.commit()

    def fake_connector(*args, **kwargs):
        class StubConnector:
            async def send_message(self, **_: object) -> dict:
                return {
                    "success": True,
                    "provider_message_id": "worker-1",
                    "response": {"status": "ok"},
                }

        return StubConnector()

    monkeypatch.setattr(delivery_module, "get_connector", fake_connector)

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    store = CircuitBreakerStore(fake_redis, key_prefix="circuit-test", threshold=1, cooldown_seconds=5)
    monkeypatch.setattr(message_worker, "get_circuit_breaker_store", lambda: store)

    context = DeliveryContext(
        job_id=str(job.id),
        org_id=str(provider.org_id),
        routing_decision={
            "provider_id": str(provider.id),
            "fallback_chain": [],
            "rule_id": None,
            "rule_name": "test",
        },
        estimated_cost_minor=85,
        baseline_cost_minor=85,
    )

    metric = MESSAGES_SEND_COUNTER.labels(status="delivered", provider=provider.name, channel="whatsapp")
    before = metric._value.get()

    result = message_worker.process_message_send(context=context.to_payload(), db_session=db_session)

    assert result["status"] == JobStatusEnum.delivered.value
    assert result["provider"] == provider.name
    assert result["channel"] == "whatsapp"

    refreshed_job = db_session.get(MessageJob, job.id)
    assert refreshed_job.status == JobStatusEnum.delivered

    after = metric._value.get()
    assert after == before + 1
