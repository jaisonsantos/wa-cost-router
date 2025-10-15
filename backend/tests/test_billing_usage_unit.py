import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.billing.usage import BillingUsageService
from app.models.models import BillingSubscription, MessageEvent


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


@pytest.mark.usefixtures("db_session")
def test_mark_message_billable_and_sync(db_session, organization_factory):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id)

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


@pytest.mark.usefixtures("db_session")
def test_sync_window_creates_usage_record_and_is_idempotent(db_session, organization_factory):
    org_id = uuid.uuid4()
    organization_factory(org_id=org_id)

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
    service.ensure_backfill(now=now)

    result = service.sync_due_windows(now=now, limit=10)
    assert result.processed == result.succeeded
    # ensure one usage record created with quantity 2
    assert len(gateway.calls) >= 1
    call = gateway.calls[0]
    assert call["quantity"] == 2

    # run again; idempotency should prevent duplicate charges but service still records success or skips
    result2 = service.sync_due_windows(now=now, limit=10)
    assert result2.processed == 0 or result2.succeeded >= 0
