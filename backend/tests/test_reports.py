import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.reports import get_dashboard_metrics, get_provider_metrics
from app.core.database import Base
from app.models.models import (
    AttemptStatusEnum,
    JobStatusEnum,
    DeliveryAttempt,
    MessageEvent,
    MessageJob,
    Organization,
    Provider,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_provider_metrics_aggregates_only_provider_events(session):
    org_id = uuid.uuid4()
    now = datetime.utcnow()

    org = Organization(id=org_id, name="Org")
    provider_a = Provider(id=uuid.uuid4(), org_id=org_id, name="Provider A", type="sms")
    provider_b = Provider(id=uuid.uuid4(), org_id=org_id, name="Provider B", type="sms")

    session.add_all([org, provider_a, provider_b])
    session.commit()

    job_a = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-a",
        to_number="123",
        template_id="tmpl",
        status=JobStatusEnum.delivered,
        created_at=now,
    )
    job_b = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-b",
        to_number="456",
        template_id="tmpl",
        status=JobStatusEnum.delivered,
        created_at=now,
    )

    session.add_all([job_a, job_b])
    session.commit()

    attempt_a = DeliveryAttempt(
        id=uuid.uuid4(),
        message_job_id=job_a.id,
        provider_id=provider_a.id,
        attempt_number=1,
        status=AttemptStatusEnum.success,
        latency_ms=100,
        timestamp=now,
    )
    attempt_b = DeliveryAttempt(
        id=uuid.uuid4(),
        message_job_id=job_b.id,
        provider_id=provider_b.id,
        attempt_number=1,
        status=AttemptStatusEnum.success,
        latency_ms=120,
        timestamp=now,
    )

    session.add_all([attempt_a, attempt_b])

    event_a = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job_a.id,
        provider_event_id="evt-a",
        direction="outbound",
        timestamp_provider=now,
        unit_cost_minor=150,
    )
    event_b = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job_b.id,
        provider_event_id="evt-b",
        direction="outbound",
        timestamp_provider=now,
        unit_cost_minor=250,
    )

    session.add_all([event_a, event_b])
    session.commit()

    metrics = get_provider_metrics(days=7, current_user={"org_id": org_id}, db=session)
    metrics_by_provider = {metric.provider_name: metric for metric in metrics}

    assert metrics_by_provider["Provider A"].total_cost_minor == 150
    assert metrics_by_provider["Provider B"].total_cost_minor == 250
    assert metrics_by_provider["Provider A"].total_sent == 1
    assert metrics_by_provider["Provider B"].total_sent == 1


def test_dashboard_metrics_includes_baseline_and_savings(session):
    org_id = uuid.uuid4()
    now = datetime.utcnow()

    org = Organization(id=org_id, name="Org")
    provider = Provider(id=uuid.uuid4(), org_id=org_id, name="Provider", type="whatsapp")

    session.add_all([org, provider])
    session.commit()

    job_a = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-1",
        to_number="+5511987654321",
        template_id="welcome",
        template_category="MARKETING",
        country_iso="BR",
        status=JobStatusEnum.delivered,
        created_at=now,
    )
    job_b = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-2",
        to_number="+5511987654322",
        template_id="welcome",
        template_category="MARKETING",
        country_iso="BR",
        status=JobStatusEnum.delivered,
        created_at=now,
    )

    session.add_all([job_a, job_b])
    session.commit()

    attempt_a = DeliveryAttempt(
        id=uuid.uuid4(),
        message_job_id=job_a.id,
        provider_id=provider.id,
        attempt_number=1,
        status=AttemptStatusEnum.success,
        latency_ms=90,
        timestamp=now,
    )
    attempt_b = DeliveryAttempt(
        id=uuid.uuid4(),
        message_job_id=job_b.id,
        provider_id=provider.id,
        attempt_number=1,
        status=AttemptStatusEnum.success,
        latency_ms=110,
        timestamp=now,
    )

    session.add_all([attempt_a, attempt_b])

    event_a = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job_a.id,
        provider_event_id="evt-1",
        direction="outbound",
        template_name="welcome",
        category="MARKETING",
        country_iso="BR",
        timestamp_provider=now,
        delivery_status="delivered",
        unit_cost_minor=180,
        baseline_cost_minor=300,
        currency="USD",
    )
    event_b = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job_b.id,
        provider_event_id="evt-2",
        direction="outbound",
        template_name="welcome",
        category="MARKETING",
        country_iso="BR",
        timestamp_provider=now,
        delivery_status="delivered",
        unit_cost_minor=220,
        baseline_cost_minor=300,
        currency="USD",
    )

    session.add_all([event_a, event_b])
    session.commit()

    metrics = get_dashboard_metrics(days=7, current_user={"org_id": org_id}, db=session)

    assert metrics.total_cost_minor == 400
    assert metrics.baseline_cost_minor == 600
    assert metrics.saved_minor == 200
    assert metrics.total_messages == 2
    assert metrics.success_rate == pytest.approx(100.0)
    assert metrics.avg_latency_ms == pytest.approx(100.0)
    assert metrics.top_countries and metrics.top_countries[0]["cost_minor"] == 400
    assert metrics.top_templates and metrics.top_templates[0]["cost_minor"] == 400
    assert any("economizou" in rec.lower() for rec in metrics.recommendations)
