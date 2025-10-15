from __future__ import annotations

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

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.billing import _handle_invoice_paid  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.metrics import BILLING_TAX_APPLIED_TOTAL  # noqa: E402
from app.models.models import (  # noqa: E402
    BillingInvoice,
    BillingStatusEnum,
    BillingSubscription,
    Organization,
    User,
)


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
    organization = Organization(id=org_id, name="Tax Org")
    user = User(id=uuid.uuid4(), email="billing@example.com", password_hash="x")
    subscription = BillingSubscription(
        org_id=org_id,
        stripe_customer_id="cus_tax",
        status=BillingStatusEnum.active,
    )
    db_session.add_all([organization, user, subscription])
    db_session.commit()
    return organization, user, subscription


def _reset_tax_metric(org_id: uuid.UUID) -> None:
    try:
        BILLING_TAX_APPLIED_TOTAL.remove(str(org_id))
    except KeyError:
        pass


def _metric_value(org_id: uuid.UUID) -> float:
    return BILLING_TAX_APPLIED_TOTAL.labels(org_id=str(org_id))._value.get()


def test_invoice_paid_persists_tax_amount(db_session, org_subscription):
    organization, _, subscription = org_subscription
    _reset_tax_metric(organization.id)

    invoice_payload = {
        "id": "in_123",
        "customer": "cus_tax",
        "status": "paid",
        "currency": "usd",
        "created": int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()),
        "subtotal": 10000,
        "total": 11200,
        "total_tax_amounts": [
            {"amount": 1200},
        ],
        "lines": {
            "data": [
                {
                    "type": "subscription",
                    "quantity": 200,
                    "period": {"start": 1735689600, "end": 1738281600},
                    "price": {
                        "id": "price_123",
                        "tax_behavior": "exclusive",
                    },
                }
            ]
        },
    }

    _handle_invoice_paid(db_session, invoice_payload)

    invoice = (
        db_session.query(BillingInvoice)
        .filter(BillingInvoice.stripe_invoice_id == "in_123")
        .one()
    )
    db_session.refresh(subscription)

    assert invoice.tax_amount_total_minor == 1200
    assert invoice.tax_behavior == "exclusive"
    assert subscription.tax_amount_total_minor == 1200
    assert _metric_value(organization.id) == 1200.0


def test_invoice_updates_adjust_tax_totals(db_session, org_subscription):
    organization, _, subscription = org_subscription
    _reset_tax_metric(organization.id)

    initial_payload = {
        "id": "in_456",
        "customer": "cus_tax",
        "status": "paid",
        "currency": "usd",
        "subtotal": 5000,
        "total": 5600,
        "total_tax_amounts": [{"amount": 600}],
        "lines": {"data": [{"type": "subscription", "quantity": 120, "price": {}}]},
    }

    updated_payload = {
        **initial_payload,
        "total_tax_amounts": [{"amount": 700}],
        "total": 5700,
    }

    _handle_invoice_paid(db_session, initial_payload)
    _handle_invoice_paid(db_session, updated_payload)

    invoice = (
        db_session.query(BillingInvoice)
        .filter(BillingInvoice.stripe_invoice_id == "in_456")
        .one()
    )
    db_session.refresh(subscription)

    assert invoice.tax_amount_total_minor == 700
    assert subscription.tax_amount_total_minor == 700
    assert _metric_value(organization.id) == 700.0
