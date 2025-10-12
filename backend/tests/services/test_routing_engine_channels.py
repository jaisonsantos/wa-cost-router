import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
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
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactStatusEnum,
    OptInStatusEnum,
    Organization,
    Provider,
    RateCard,
    RoutingRule,
)  # noqa: E402
from app.services.routing import ContactOptOutError  # noqa: E402
from app.services.routing_engine import RoutingEngine  # noqa: E402


class _ClosedCircuitBreaker:
    def get_state(self, provider_id: str) -> CircuitState:  # pragma: no cover - simple stub
        return CircuitState("closed", 0, None, None)


@compiles(PGUUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):  # pragma: no cover - sqlite shim
    return "TEXT"


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


def _create_provider(session, org_id, name, *, channel):
    provider = Provider(
        org_id=org_id,
        name=name,
        type=channel,
        status="active",
    )
    session.add(provider)
    session.flush()

    rate = RateCard(
        provider_id=provider.id,
        effective_from=datetime.utcnow(),
        source="test",
        country_iso="BR",
        category="MARKETING",
        unit_cost_minor=100 if channel == "whatsapp" else 90,
        currency="USD",
    )
    session.add(rate)

    return provider


def test_select_provider_skips_rules_with_different_channel(db_session):
    org_id = uuid.uuid4()
    db_session.add(Organization(id=org_id, name="Org"))

    whatsapp = _create_provider(db_session, org_id, "wa", channel="whatsapp")
    sms = _create_provider(db_session, org_id, "sms", channel="sms")

    rule = RoutingRule(
        org_id=org_id,
        name="wa-only",
        is_enabled=True,
        conditions_json=[{"type": "country", "values": ["BR"]}],
        actions_json={
            "channel": "whatsapp",
            "primary_provider": str(whatsapp.id),
            "fallback_chain": [],
        },
        priority=1,
    )
    db_session.add(rule)
    db_session.commit()

    engine = RoutingEngine(db_session, org_id, circuit_breaker=_ClosedCircuitBreaker())

    decision = engine.select_provider(
        country_iso="BR",
        category="MARKETING",
        template_id=None,
        channel="sms",
        send_time=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert decision is not None
    assert decision["provider_id"] == str(sms.id)


def test_select_provider_filters_legacy_fallbacks_by_channel(db_session):
    org_id = uuid.uuid4()
    db_session.add(Organization(id=org_id, name="Org"))

    primary = _create_provider(db_session, org_id, "wa-primary", channel="whatsapp")
    whatsapp_fallback = _create_provider(db_session, org_id, "wa-fallback", channel="whatsapp")
    sms = _create_provider(db_session, org_id, "sms-provider", channel="sms")

    legacy_rule = RoutingRule(
        org_id=org_id,
        name="legacy",
        is_enabled=True,
        conditions_json=[{"type": "country", "values": ["BR"]}],
        actions_json={
            "primary_provider": str(primary.id),
            "fallback_chain": [str(whatsapp_fallback.id), str(sms.id)],
        },
        priority=5,
    )
    db_session.add(legacy_rule)
    db_session.commit()

    engine = RoutingEngine(db_session, org_id, circuit_breaker=_ClosedCircuitBreaker())

    decision = engine.select_provider(
        country_iso="BR",
        category="MARKETING",
        template_id=None,
        channel="whatsapp",
        send_time=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert decision is not None
    assert decision["provider_id"] == str(primary.id)
    # Only whatsapp providers should remain in the fallback chain
    assert decision["fallback_chain"] == [str(whatsapp_fallback.id)]


def test_select_provider_raises_without_channel_consent(db_session):
    org_id = uuid.uuid4()
    organization = Organization(id=org_id, name="Org")
    db_session.add(organization)

    provider = _create_provider(db_session, org_id, "wa", channel="whatsapp")

    rule = RoutingRule(
        org_id=org_id,
        name="wa-only",
        is_enabled=True,
        conditions_json=[{"type": "country", "values": ["BR"]}],
        actions_json={
            "channel": "whatsapp",
            "primary_provider": str(provider.id),
            "fallback_chain": [],
        },
        priority=1,
    )
    db_session.add(rule)

    contact = Contact(
        org_id=org_id,
        phone="+5511999999999",
        status=ContactStatusEnum.active,
    )
    db_session.add(contact)
    db_session.flush()

    opt_in = ContactChannelOptIn(
        org_id=org_id,
        contact_id=contact.id,
        channel="sms",
        channel_address="+5511999999999",
        status=OptInStatusEnum.granted,
        version=1,
        source="import",
    )
    db_session.add(opt_in)
    db_session.commit()

    engine = RoutingEngine(db_session, org_id, circuit_breaker=_ClosedCircuitBreaker())

    with pytest.raises(ContactOptOutError):
        engine.select_provider(
            country_iso="BR",
            category="MARKETING",
            template_id=None,
            channel="whatsapp",
            contact_address="+5511999999999",
            send_time=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
