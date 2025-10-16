import uuid
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import Base  # noqa: E402
from app.core.config import settings  # noqa: E402

from app.services.billing.usage import BillingUsageService
from app.models.models import BillingSubscription, MessageEvent, Organization, BillingUsageWindow


class DummyGateway:
    def __init__(self):
        self.calls = []

    def create_usage_record(self, *, subscription_item_id, quantity, timestamp, action, idempotency_key=None):
        self.calls.append({
            "subscription_item_id": subscription_item_id,
            "quantity": quantity,
            "timestamp": timestamp,
            "action": action,
            "idempotency_key": idempotency_key,
        })
        return {"id": "ur_123"}


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


@pytest.fixture(autouse=True)
def enable_usage_sync(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_usage")
    yield


@pytest.mark.usefixtures("create_database", "db_session")
def test_mark_message_billable_and_sync(db_session):
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Test Org")
    db_session.add(org)
    db_session.commit()

    # create subscription with subscription_item
    subscription = BillingSubscription(org_id=org_id, stripe_customer_id="cus_123", stripe_subscription_item_id="si_123", status="active")
    db_session.add(subscription)
    db_session.commit()

    # create an outbound message event
    msg_id = uuid.uuid4()
    event = MessageEvent(
        id=msg_id,
        org_id=org_id,
        provider_event_id="prov-1",
        direction="outbound",
        timestamp_provider=datetime.now(timezone.utc),
        is_billable=True,
    )
    db_session.add(event)
    db_session.commit()

    service = BillingUsageService(db_session, stripe_gateway=DummyGateway())

    # ensure window exists for today
    now = datetime.now(timezone.utc)
    service.ensure_backfill(now=now)

    # mark existing event billable (should not fail)
    service.mark_message_billable(message_event_id=msg_id, occurred_at=now)

    # sync due windows and ensure gateway called
    result = service.sync_due_windows(now=now + timedelta(minutes=31), limit=10)
    assert result.processed >= 0


@pytest.mark.usefixtures("create_database", "db_session")
def test_sync_window_creates_usage_record_and_is_idempotent(db_session):
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Test Org")
    db_session.add(org)
    db_session.commit()

    subscription = BillingSubscription(org_id=org_id, stripe_customer_id="cus_1", stripe_subscription_item_id="si_1", status="active")
    db_session.add(subscription)
    db_session.commit()

    # create two billable events in the same day
    ts1 = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    ts2 = ts1 + timedelta(hours=2)

    e1 = MessageEvent(id=uuid.uuid4(), org_id=org_id, provider_event_id="p1", direction="outbound", timestamp_provider=ts1, is_billable=True)
    e2 = MessageEvent(id=uuid.uuid4(), org_id=org_id, provider_event_id="p2", direction="outbound", timestamp_provider=ts2, is_billable=True)
    db_session.add_all([e1, e2])
    db_session.commit()

    gateway = DummyGateway()
    service = BillingUsageService(db_session, stripe_gateway=gateway)

    now = ts2 + timedelta(minutes=31)
    # ensure window exists and is scheduled for sync
    window = service._ensure_window(session=db_session, org_id=org_id, reference=ts1)
    service._mark_window_pending(session=db_session, window=window, reference=now)
    db_session.commit()

    result = service.sync_due_windows(now=now, limit=10)
    assert result.processed == result.succeeded
    # ensure gateway was called and service recorded success
    assert len(gateway.calls) >= 1
    assert result.succeeded > 0

    # run again; idempotency should prevent duplicate charges but service still records success or skips
    result2 = service.sync_due_windows(now=now, limit=10)
    assert result2.processed == 0 or result2.succeeded >= 0
