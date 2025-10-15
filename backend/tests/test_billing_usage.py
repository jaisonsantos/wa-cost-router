import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.models import (  # noqa: E402
    BillingSubscription,
    BillingUsageWindow,
    BillingUsageWindowStatusEnum,
    MessageEvent,
    Organization,
)  # noqa: E402
import app.services.billing.usage as usage_module  # noqa: E402
from app.services.billing.usage import BillingUsageService, UsageSyncResult  # noqa: E402
from app.workers.billing_usage import (  # noqa: E402
    enqueue_billing_usage_sync,
    enqueue_usage_window_event,
    process_billing_usage_sync,
    process_usage_window_event,
)  # noqa: E402


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def enable_usage_sync(monkeypatch):
    """Ensure billing usage features are enabled for tests by default."""

    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_usage")
    yield


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


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
def organization(db_session):
    org = Organization(id=uuid.uuid4(), name="Usage Org")
    db_session.add(org)
    db_session.commit()
    return org


class DummyGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_usage_record(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id="ur_123")


class FailingGateway(DummyGateway):
    def __init__(self, *, error: Exception) -> None:
        super().__init__()
        self._error = error

    def create_usage_record(self, **kwargs):  # noqa: D401
        super().create_usage_record(**kwargs)
        raise self._error


def _create_message_event(db_session, *, org_id: uuid.UUID, occurred_at: datetime) -> MessageEvent:
    event = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=None,
        connection_id=None,
        channel="whatsapp",
        channel_address="+123456789",
        contact_id=None,
        provider_event_id=str(uuid.uuid4()),
        direction="outbound",
        template_name="welcome",
        category="marketing",
        country_iso="ES",
        timestamp_provider=occurred_at,
        delivery_status="delivered",
        unit_cost_minor=10,
        baseline_cost_minor=12,
        currency="eur",
        attributes={},
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_mark_message_billable_creates_window(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    event_time = datetime.now(timezone.utc) - timedelta(days=1)
    event = _create_message_event(db_session, org_id=organization.id, occurred_at=event_time)

    service = BillingUsageService(db_session)
    service.mark_message_billable(message_event_id=event.id)
    db_session.commit()

    refreshed = db_session.get(MessageEvent, event.id)
    assert refreshed.is_billable is True

    window = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .one()
    )
    assert window.status == BillingUsageWindowStatusEnum.pending
    assert window.next_run_at is not None
    window_start = BillingUsageService._ensure_tz(window.period_start)
    window_end = BillingUsageService._ensure_tz(window.period_end)
    assert window_start <= event_time < window_end


def test_process_usage_window_event_marks_billable(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    event_time = datetime.now(timezone.utc)
    event = _create_message_event(db_session, org_id=organization.id, occurred_at=event_time)

    result = process_usage_window_event(
        message_event_id=str(event.id),
        occurred_at=event_time,
        db_session=db_session,
    )

    assert result["status"] == "queued"
    refreshed = db_session.get(MessageEvent, event.id)
    assert refreshed.is_billable is True


def test_process_usage_window_event_skips_when_disabled(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", False)
    event_time = datetime.now(timezone.utc)
    event = _create_message_event(db_session, org_id=organization.id, occurred_at=event_time)
    event.is_billable = True
    db_session.commit()

    result = process_usage_window_event(
        message_event_id=str(event.id),
        occurred_at=event_time,
        db_session=db_session,
    )

    assert result["status"] == "disabled"
    refreshed = db_session.get(MessageEvent, event.id)
    assert refreshed.is_billable is True


def test_mark_message_billable_is_idempotent_for_same_window(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    moment = datetime.now(timezone.utc)
    first = _create_message_event(db_session, org_id=organization.id, occurred_at=moment)
    second = _create_message_event(db_session, org_id=organization.id, occurred_at=moment + timedelta(minutes=5))

    service = BillingUsageService(db_session)
    service.mark_message_billable(message_event_id=first.id)
    service.mark_message_billable(message_event_id=second.id)
    db_session.commit()

    windows = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .all()
    )
    assert len(windows) == 1
    assert windows[0].status == BillingUsageWindowStatusEnum.pending


def test_mark_message_billable_generates_window_id(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    event = _create_message_event(
        db_session,
        org_id=organization.id,
        occurred_at=datetime.now(timezone.utc),
    )

    original_uuid4 = usage_module.uuid.uuid4
    generated: list[uuid.UUID] = []

    def fake_uuid4() -> uuid.UUID:
        value = original_uuid4()
        generated.append(value)
        return value

    monkeypatch.setattr(usage_module.uuid, "uuid4", fake_uuid4)

    service = BillingUsageService(db_session)
    service.mark_message_billable(message_event_id=event.id)
    db_session.commit()

    window = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .one()
    )
    assert generated, "expected uuid.uuid4 to be invoked"
    assert str(window.id) == str(generated[0])


def test_mark_message_billable_handles_pending_event(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    occurred_at = datetime.now(timezone.utc)

    event = MessageEvent(
        id=uuid.uuid4(),
        org_id=organization.id,
        message_job_id=None,
        connection_id=None,
        channel="whatsapp",
        channel_address="+123456789",
        contact_id=None,
        provider_event_id=str(uuid.uuid4()),
        direction="outbound",
        template_name="welcome",
        category="marketing",
        country_iso="ES",
        timestamp_provider=occurred_at,
        delivery_status="delivered",
        unit_cost_minor=10,
        baseline_cost_minor=12,
        currency="eur",
        attributes={},
    )
    db_session.add(event)

    service = BillingUsageService(db_session)
    service.mark_message_billable(message_event_id=event.id)
    db_session.commit()

    db_session.refresh(event)
    assert event.is_billable is True

    window = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .one()
    )
    assert window.status == BillingUsageWindowStatusEnum.pending


def test_mark_message_billable_recovers_from_integrity_error(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    event = _create_message_event(
        db_session,
        org_id=organization.id,
        occurred_at=datetime.now(timezone.utc),
    )

    service = BillingUsageService(db_session)

    def boom(*args, **kwargs):  # noqa: ANN001
        raise IntegrityError("insert", {}, Exception("duplicate key"))

    monkeypatch.setattr(service, "_ensure_window", boom)

    service.mark_message_billable(message_event_id=event.id)

    # commit should not fail even though ensure_window raised
    db_session.commit()

    refreshed = db_session.get(MessageEvent, event.id)
    assert refreshed.is_billable is True

    windows = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .all()
    )
    assert windows == []


def test_mark_message_billable_does_not_close_parent_connection(
    db_session, organization, monkeypatch
):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)

    occurred_at = datetime.now(timezone.utc)
    event = _create_message_event(
        db_session,
        org_id=organization.id,
        occurred_at=occurred_at,
    )

    connection = db_session.connection()
    assert not connection.closed

    service = BillingUsageService(db_session)
    service.mark_message_billable(message_event_id=event.id, occurred_at=occurred_at)
    db_session.commit()

    assert not connection.closed

    # Ability to execute further queries without raising signals the parent
    # session/connection remains usable after marking the event billable.
    assert db_session.query(MessageEvent).first() is not None


def test_sync_due_windows_sends_usage_and_updates_state(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    subscription = BillingSubscription(
        org_id=organization.id,
        stripe_customer_id="cus_sync",
        stripe_subscription_id="sub_sync",
        status="active",
        stripe_subscription_item_id="si_usage",
    )
    db_session.add(subscription)
    db_session.commit()

    occurred_at = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    event = _create_message_event(db_session, org_id=organization.id, occurred_at=occurred_at)

    service = BillingUsageService(db_session, stripe_gateway=DummyGateway())
    service.mark_message_billable(message_event_id=event.id, occurred_at=occurred_at)

    now = datetime(2025, 1, 3, 0, 5, tzinfo=timezone.utc)
    result = service.sync_due_windows(now=now)
    assert result.processed == 1
    assert result.succeeded == 1
    assert result.failed == 0

    window = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .one()
    )
    assert window.status == BillingUsageWindowStatusEnum.succeeded
    assert window.last_synced_quantity == 1
    assert window.next_run_at is None

    gateway_calls = service._stripe_gateway.calls  # type: ignore[attr-defined]
    assert gateway_calls
    call = gateway_calls[0]
    assert call["subscription_item_id"] == "si_usage"
    assert call["quantity"] == 1
    assert call["action"] == "set"


def test_sync_due_windows_handles_retry(db_session, organization, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_GRACE_MINUTES", 0)
    monkeypatch.setattr(settings, "BILLING_USAGE_LOOKBACK_DAYS", 1)
    monkeypatch.setattr(settings, "BILLING_USAGE_RETRY_BASE_SECONDS", 1)
    monkeypatch.setattr(settings, "BILLING_USAGE_RETRY_MAX_SECONDS", 5)
    monkeypatch.setattr(settings, "BILLING_USAGE_MAX_RETRIES", 5)

    subscription = BillingSubscription(
        org_id=organization.id,
        stripe_customer_id="cus_retry",
        stripe_subscription_id="sub_retry",
        status="active",
        stripe_subscription_item_id="si_retry",
    )
    db_session.add(subscription)
    db_session.commit()

    occurred_at = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)
    event = _create_message_event(db_session, org_id=organization.id, occurred_at=occurred_at)

    failing_gateway = FailingGateway(error=Exception("stripe outage"))
    service = BillingUsageService(db_session, stripe_gateway=failing_gateway)
    service.mark_message_billable(message_event_id=event.id, occurred_at=occurred_at)

    first_now = datetime(2025, 1, 3, 0, 1, tzinfo=timezone.utc)
    result = service.sync_due_windows(now=first_now)
    assert result.processed >= 1
    assert result.failed >= 1

    windows = (
        db_session.query(BillingUsageWindow)
        .filter(BillingUsageWindow.org_id == organization.id)
        .all()
    )
    assert windows, "expected at least one usage window"
    window = windows[0]
    assert window.status == BillingUsageWindowStatusEnum.failed
    assert window.retry_count == 1
    assert window.next_run_at is not None

    success_gateway = DummyGateway()
    recovery_service = BillingUsageService(db_session, stripe_gateway=success_gateway)
    second_now = window.next_run_at + timedelta(seconds=2)
    result = recovery_service.sync_due_windows(now=second_now)
    assert result.succeeded >= 1

    db_session.refresh(window)
    assert window.status == BillingUsageWindowStatusEnum.succeeded
    assert window.retry_count == 0
    assert window.last_synced_quantity == 1


def test_process_billing_usage_sync_disabled(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", False)
    response = process_billing_usage_sync(now=datetime.now(timezone.utc))
    assert response["status"] == "disabled"
    assert response["processed"] == 0


def test_process_billing_usage_sync_runs(monkeypatch, db_session):
    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_usage")

    called = {}

    def fake_sync(self, now=None, limit=None):  # noqa: ANN001
        called["now"] = now
        called["limit"] = limit
        return UsageSyncResult(processed=1, succeeded=1)

    monkeypatch.setattr(BillingUsageService, "sync_due_windows", fake_sync)
    result = process_billing_usage_sync(now=datetime.now(timezone.utc), db_session=db_session, limit=5)
    assert result["processed"] == 1
    assert result["status"] == "completed"
    assert called["limit"] == 5


def test_service_disabled_without_stripe_secret(db_session, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")

    service = BillingUsageService(db_session)

    assert service.sync_enabled is False


def test_enqueue_billing_usage_sync(monkeypatch):
    captured = {}

    class DummyQueue:
        def enqueue(self, func, kwargs=None):  # noqa: ANN001
            captured["kwargs"] = kwargs
            return SimpleNamespace(id="job-789")

    monkeypatch.setattr("app.workers.billing_usage.get_queue", lambda: DummyQueue())
    job_id = enqueue_billing_usage_sync(limit=3)
    assert job_id == "job-789"
    assert captured["kwargs"]["limit"] == 3
