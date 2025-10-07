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

from app.api.reports import get_provider_metrics
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
