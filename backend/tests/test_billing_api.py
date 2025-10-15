import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
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

from app.api.dependencies import get_current_user  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
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
def client(db_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    def override_current_user():
        return {"user_id": user_id, "org_id": org_id}

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client, org_id, user_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


class DummyGateway:
    def __init__(self):
        self.checkout_payloads: list[dict[str, object]] = []
        self.created_customers: list[dict[str, object]] = []

    def create_customer(self, **kwargs):
        self.created_customers.append(kwargs)
        return SimpleNamespace(id="cus_test")

    def create_checkout_session(self, **kwargs):
        self.checkout_payloads.append(kwargs)
        return SimpleNamespace(url="https://stripe.test/checkout")


def test_checkout_creates_customer_and_session(client, db_session, monkeypatch):
    test_client, org_id, user_id = client

    organization = Organization(id=org_id, name="Checkout Org")
    user = User(id=user_id, email="owner@example.com", password_hash="x")
    db_session.add_all([organization, user])
    db_session.commit()

    gateway = DummyGateway()
    monkeypatch.setattr("app.api.billing.get_stripe_gateway", lambda: gateway)

    response = test_client.post(
        "/billing/checkout",
        json={
            "price_id": "price_123",
            "success_url": "https://app.local/success",
            "cancel_url": "https://app.local/cancel",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["checkout_url"] == "https://stripe.test/checkout"

    subscription = (
        db_session.query(BillingSubscription)
        .filter(BillingSubscription.org_id == org_id)
        .first()
    )
    assert subscription is not None
    assert subscription.stripe_customer_id == "cus_test"
    assert subscription.price_id == "price_123"
    assert gateway.checkout_payloads
    checkout_payload = gateway.checkout_payloads[0]
    assert checkout_payload["customer"] == "cus_test"
    assert checkout_payload["metadata"]["org_id"] == str(org_id)


def test_webhook_updates_subscription(client, db_session, monkeypatch):
    test_client, org_id, user_id = client

    organization = Organization(id=org_id, name="Webhook Org")
    user = User(id=user_id, email="owner@example.com", password_hash="x")
    subscription = BillingSubscription(
        org_id=org_id,
        stripe_customer_id="cus_webhook",
        status=BillingStatusEnum.incomplete,
    )
    db_session.add_all([organization, user, subscription])
    db_session.commit()

    period_end = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())

    subscription_event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "status": "active",
                "customer": "cus_webhook",
                "cancel_at_period_end": False,
                "current_period_end": period_end,
                "items": {
                    "data": [
                        {
                            "id": "si_123",
                            "quantity": 250,
                            "price": {
                                "id": "price_456",
                                "currency": "eur",
                                "unit_amount": 7900,
                                "nickname": "Professional",
                                "metadata": {"message_quota": "1000"},
                            },
                        }
                    ]
                },
                "default_payment_method": {
                    "card": {"brand": "visa", "last4": "4242"}
                },
                "metadata": {"org_id": str(org_id)},
            }
        },
    }

    invoice_event = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "customer": "cus_webhook",
                "status": "paid",
                "hosted_invoice_url": "https://stripe.test/invoice",
                "lines": {
                    "data": [
                        {
                            "type": "subscription",
                            "quantity": 300,
                        }
                    ]
                },
            }
        },
    }

    events = [subscription_event, invoice_event]

    def fake_verify(payload, signature):
        return events.pop(0)

    monkeypatch.setattr("app.api.billing.verify_webhook_event", fake_verify)

    response = test_client.post(
        "/billing/webhook",
        data="{}",
        headers={"Stripe-Signature": "sig"},
    )
    assert response.status_code == 200

    response = test_client.post(
        "/billing/webhook",
        data="{}",
        headers={"Stripe-Signature": "sig"},
    )
    assert response.status_code == 200

    db_session.refresh(subscription)
    assert subscription.status == BillingStatusEnum.active
    assert subscription.plan_nickname == "Professional"
    assert subscription.amount_minor == 7900
    assert subscription.currency == "eur"
    assert subscription.message_quota == 1000
    assert subscription.message_usage == 300
    assert subscription.current_period_end is not None
    assert subscription.stripe_subscription_item_id == "si_123"
    normalized_period_end = subscription.current_period_end.replace(
        tzinfo=subscription.current_period_end.tzinfo or timezone.utc,
    )
    assert normalized_period_end == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert subscription.default_payment_method == {"brand": "visa", "last4": "4242"}
    assert subscription.latest_invoice_url == "https://stripe.test/invoice"

    summary_response = test_client.get("/billing/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["plan_name"] == "Professional"
    assert summary["plan_status"] == "active"
    assert summary["message_usage"] == 300
    assert summary["message_quota"] == 1000
    assert summary["payment_method_last4"] == "4242"


def test_usage_sync_endpoint_requires_flag(client, monkeypatch):
    test_client, org_id, user_id = client

    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_usage")

    monkeypatch.setattr("app.api.billing.enqueue_billing_usage_sync", lambda: "job-usage")

    response = test_client.post("/billing/usage/sync")
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] == "job-usage"
    assert payload["status"] == "enqueued"


def test_usage_sync_endpoint_returns_503_when_disabled(client, monkeypatch):
    test_client, org_id, user_id = client

    monkeypatch.setattr(settings, "BILLING_USAGE_SYNC_ENABLED", False)

    response = test_client.post("/billing/usage/sync")
    assert response.status_code == 503
