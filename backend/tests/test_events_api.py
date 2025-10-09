import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

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


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import MessageEvent, Organization  # noqa: E402


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


def test_events_endpoint_accepts_trailing_and_missing_slash(client, db_session):
    test_client, org_id = client

    organization = Organization(id=org_id, name="Events Org")
    db_session.add(organization)

    event = MessageEvent(
        org_id=org_id,
        provider_event_id="evt-001",
        direction="outbound",
        timestamp_provider=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.commit()

    response_no_slash = test_client.get("/events", allow_redirects=False)
    assert response_no_slash.status_code == 200
    payload = response_no_slash.json()
    assert isinstance(payload, list)
    assert len(payload) == 1

    response_with_slash = test_client.get("/events/", allow_redirects=False)
    assert response_with_slash.status_code == 200
    assert response_with_slash.json() == payload
