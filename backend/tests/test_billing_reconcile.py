from __future__ import annotations

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
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.metrics import BILLING_RECONCILE_DRIFT  # noqa: E402
from app.models.models import (  # noqa: E402
    BillingInvoice,
    BillingStatusEnum,
    BillingSubscription,
    Organization,
)
from app.workers import billing_reconcile  # noqa: E402


TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


@pytest.fixture(scope="session", autouse=True)
def create_database():
    billing_reconcile.SessionLocal.configure(bind=TEST_ENGINE)  # type: ignore[attr-defined]
    billing_reconcile.SessionLocal().close()
    from app.core.database import Base

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
def org_subscription(db_session):
    org_id = uuid.uuid4()
    organization = Organization(id=org_id, name="Reconcile Org")
    subscription = BillingSubscription(
        org_id=org_id,
        stripe_customer_id="cus_reconcile",
        status=BillingStatusEnum.active,
        tax_amount_total_minor=500,
    )
    db_session.add_all([organization, subscription])
    db_session.commit()
    return organization, subscription


def _reset_drift_metric(org_id: uuid.UUID) -> None:
    try:
        BILLING_RECONCILE_DRIFT.remove(str(org_id))
    except KeyError:
        pass


def _metric_value(org_id: uuid.UUID) -> float:
    return BILLING_RECONCILE_DRIFT.labels(org_id=str(org_id))._value.get()


class DummyGateway:
    def __init__(self, responses: dict[str, dict[str, int]]):
        self.responses = responses

    def retrieve_invoice(self, invoice_id: str):
        payload = self.responses[invoice_id]
        return SimpleNamespace(**payload)


def test_reconcile_without_drift(db_session, org_subscription, monkeypatch):
    organization, subscription = org_subscription
    _reset_drift_metric(organization.id)

    now = datetime.now(timezone.utc)
    invoice = BillingInvoice(
        org_id=organization.id,
        stripe_invoice_id="in_sync",
        stripe_customer_id=subscription.stripe_customer_id,
        total_minor=5500,
        tax_amount_total_minor=500,
        issued_at=now,
        updated_at=now,
    )
    db_session.add(invoice)
    db_session.commit()

    gateway = DummyGateway({"in_sync": {"total": 5500, "total_details": {"amount_tax": 500}}})
    monkeypatch.setattr(billing_reconcile, "get_stripe_gateway", lambda: gateway)

    result = billing_reconcile.process_billing_reconciliation(
        since=now - timedelta(days=1),
        until=now + timedelta(minutes=5),
        db_session=db_session,
    )

    assert result["processed"] == 1
    assert result["alerts"] == 0
    assert result["max_drift_pct"] == 0.0
    assert _metric_value(organization.id) == 0.0


def test_reconcile_emits_alert_when_drift_exceeds_threshold(db_session, org_subscription, monkeypatch, caplog):
    organization, subscription = org_subscription
    _reset_drift_metric(organization.id)

    now = datetime.now(timezone.utc)
    invoice = BillingInvoice(
        org_id=organization.id,
        stripe_invoice_id="in_drift",
        stripe_customer_id=subscription.stripe_customer_id,
        total_minor=5500,
        tax_amount_total_minor=500,
        issued_at=now,
        updated_at=now,
    )
    db_session.add(invoice)
    db_session.commit()

    gateway = DummyGateway({"in_drift": {"total": 6000, "total_details": {"amount_tax": 600}}})
    monkeypatch.setattr(billing_reconcile, "get_stripe_gateway", lambda: gateway)

    with caplog.at_level("WARNING"):
        result = billing_reconcile.process_billing_reconciliation(
            since=now - timedelta(days=1),
            until=now + timedelta(minutes=5),
            db_session=db_session,
        )

    assert result["processed"] == 1
    assert result["alerts"] == 1
    assert result["max_drift_pct"] > 1.0
    assert any("Invoice drift above threshold" in message for message in caplog.messages)
    assert _metric_value(organization.id) > 1.0
