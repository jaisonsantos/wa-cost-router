"""API contract tests for contact import job status endpoint."""

from __future__ import annotations

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

from app.api.deps import (  # noqa: E402
    CONTACTS_READ_PERMISSION,
    CONTACTS_WRITE_PERMISSION,
)
from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    ContactImportJob,
    ContactImportStatusEnum,
    Organization,
)


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


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
def client_and_org(db_session):
    org_id = uuid.uuid4()

    organization = Organization(id=org_id, name="Import Org")
    db_session.add(organization)
    db_session.flush()

    def override_current_user():
        return {
            "user_id": uuid.uuid4(),
            "org_id": org_id,
            "permissions": [
                CONTACTS_READ_PERMISSION,
                CONTACTS_WRITE_PERMISSION,
            ],
        }

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


def _create_job(*, db_session, org_id, status=ContactImportStatusEnum.pending):
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    job = ContactImportJob(
        id=job_id,
        org_id=org_id,
        requested_by="tester@example.com",
        input_uri="memory://import.csv",
        status=status,
        total_rows=5,
        processed_rows=5,
        error_rows=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(job)
    db_session.flush()
    return job


def test_retrieve_import_job_returns_payload(client_and_org, db_session):
    client, org_id = client_and_org
    job = _create_job(
        db_session=db_session,
        org_id=org_id,
        status=ContactImportStatusEnum.completed,
    )

    response = client.get(f"/contacts/imports/{job.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(job.id)
    assert payload["status"] == ContactImportStatusEnum.completed
    assert payload["processed_rows"] == 5


def test_retrieve_import_job_missing_for_other_org(client_and_org, db_session):
    client, org_id = client_and_org
    other_org_id = uuid.uuid4()

    db_session.add(Organization(id=other_org_id, name="Other Org"))
    db_session.flush()

    foreign_job = _create_job(
        db_session=db_session,
        org_id=other_org_id,
        status=ContactImportStatusEnum.failed,
    )

    response = client.get(f"/contacts/imports/{foreign_job.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Import job not found"
