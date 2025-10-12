import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
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


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    AttemptStatusEnum,
    DeliveryAttempt,
    MessageEvent,
    MessageJob,
    Organization,
    Provider,
    JobStatusEnum,
)


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


@pytest.fixture
def client(db_session):
    org_id = uuid.uuid4()

    def override_current_user():
        return {"user_id": uuid.uuid4(), "org_id": org_id}

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client, org_id

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_summary_export_csv_headers_and_content(client, db_session):
    test_client, org_id = client
    now = datetime.utcnow()

    organization = Organization(id=org_id, name="Reports Org")
    db_session.add(organization)

    job = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-1",
        to_number="+5511999999999",
        template_id="welcome",
        status=JobStatusEnum.delivered,
        created_at=now,
    )
    db_session.add(job)

    event_a = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job.id,
        provider_event_id="evt-1",
        direction="outbound",
        timestamp_provider=now,
        unit_cost_minor=100,
        baseline_cost_minor=200,
    )
    event_b = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job.id,
        provider_event_id="evt-2",
        direction="outbound",
        timestamp_provider=now,
        unit_cost_minor=100,
        baseline_cost_minor=200,
    )

    db_session.add_all([event_a, event_b])
    db_session.commit()

    response = test_client.get("/reports/summary/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert "summary-report.csv" in disposition

    lines = response.content.decode("utf-8").strip().splitlines()
    assert lines[0] == "cost_7d_minor,saved_7d_minor,pct_saved"
    assert lines[1] == "200,200,50.00"


def test_provider_metrics_export_json(client, db_session):
    test_client, org_id = client
    now = datetime.now(timezone.utc)

    organization = Organization(id=org_id, name="Reports Org")
    provider = Provider(id=uuid.uuid4(), org_id=org_id, name="Provider A", type="whatsapp")
    db_session.add_all([organization, provider])

    job = MessageJob(
        id=uuid.uuid4(),
        org_id=org_id,
        idempotency_key="job-provider",
        to_number="+5511888888888",
        template_id="welcome",
        status=JobStatusEnum.delivered,
        created_at=now,
    )
    db_session.add(job)

    attempt = DeliveryAttempt(
        id=uuid.uuid4(),
        message_job_id=job.id,
        provider_id=provider.id,
        attempt_number=1,
        status=AttemptStatusEnum.success,
        latency_ms=120,
        timestamp=now,
    )
    db_session.add(attempt)

    event = MessageEvent(
        id=uuid.uuid4(),
        org_id=org_id,
        message_job_id=job.id,
        provider_event_id="evt-provider",
        direction="outbound",
        timestamp_provider=now,
        unit_cost_minor=150,
    )
    db_session.add(event)
    db_session.commit()

    response = test_client.get("/reports/provider-metrics/export?format=json&days=7")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    disposition = response.headers["content-disposition"]
    assert "provider-metrics-report.json" in disposition

    payload = json.loads(response.content.decode("utf-8"))
    assert isinstance(payload, list)
    assert payload
    provider_metric = payload[0]
    assert provider_metric["provider_name"] == "Provider A"
    assert provider_metric["total_sent"] == 1
    assert provider_metric["total_cost_minor"] == 150
