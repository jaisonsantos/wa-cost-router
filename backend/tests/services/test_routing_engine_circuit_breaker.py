import sys
import uuid
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.circuit_breaker import CircuitState  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.security import encrypt_credentials  # noqa: E402
from app.models.models import (  # noqa: E402
    Organization,
    Provider,
    ProviderCredential,
    RateCard,
    RoutingRule,
)
from app.services.routing_engine import RoutingEngine  # noqa: E402


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def create_schema():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db_session():
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


class StubCircuitBreaker:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_state(self, provider_id: str) -> CircuitState:
        return self._mapping.get(provider_id, CircuitState("closed", 0, None, None))


def _create_provider(session, org_id, name):
    provider = Provider(
        org_id=org_id,
        name=name,
        type="whatsapp",
        status="active",
    )
    session.add(provider)
    session.flush()

    credential = ProviderCredential(
        org_id=org_id,
        provider_id=provider.id,
        credentials_encrypted=encrypt_credentials({"token": "sandbox"}),
    )
    session.add(credential)

    rate = RateCard(
        provider_id=provider.id,
        effective_from=datetime.utcnow(),
        source="test",
        country_iso="BR",
        category="MARKETING",
        unit_cost_minor=100,
        currency="USD",
    )
    session.add(rate)

    return provider


def test_routing_engine_skips_open_circuit(db_session):
    org_id = uuid.uuid4()
    organization = Organization(id=org_id, name="Org")
    db_session.add(organization)

    primary = _create_provider(db_session, org_id, "360dialog")
    fallback = _create_provider(db_session, org_id, "gupshup")

    rule = RoutingRule(
        org_id=org_id,
        name="rule",
        is_enabled=True,
        conditions_json=[{"type": "country", "values": ["BR"]}],
        actions_json={
            "primary_provider": str(primary.id),
            "fallback_chain": [str(fallback.id)],
        },
        priority=1,
    )
    db_session.add(rule)
    db_session.commit()

    store = StubCircuitBreaker(
        {
            str(primary.id): CircuitState("open", 2, None, None),
            str(fallback.id): CircuitState("closed", 0, None, None),
        }
    )

    engine = RoutingEngine(db_session, org_id, circuit_breaker=store)
    decision = engine.select_provider(
        country_iso="BR",
        category="MARKETING",
        template_id=None,
    )

    assert decision is not None
    assert decision["provider_id"] == str(fallback.id)
