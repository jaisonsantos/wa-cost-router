import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


from app.core.database import Base  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactImportJob,
    ContactImportStatusEnum,
    Organization,
)
from app.services.contacts.import_worker import (  # noqa: E402
    process_contact_import_job,
)
from app.services.storage import TemporaryObjectStorage  # noqa: E402


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def organization_id(session_factory):
    session = session_factory()
    try:
        org = Organization(id=uuid.uuid4(), name="Acme Corp")
        session.add(org)
        session.commit()
        return org.id
    finally:
        session.close()


def _create_job(session_factory, org_id, input_uri):
    session = session_factory()
    try:
        job = ContactImportJob(
            id=uuid.uuid4(),
            org_id=org_id,
            requested_by="tester",
            input_uri=input_uri,
            status=ContactImportStatusEnum.pending,
        )
        session.add(job)
        session.commit()
        return job.id
    finally:
        session.close()


def test_process_contact_import_success(tmp_path, session_factory, organization_id):
    storage = TemporaryObjectStorage(base_path=tmp_path / "storage")
    csv_content = "full_name,email,phone\nJohn Doe,john@example.com,+5511999999999\n"
    input_uri = storage.store_bytes(
        csv_content.encode("utf-8"),
        prefix="contact-imports",
        suffix=".csv",
    )

    job_id = _create_job(session_factory, organization_id, input_uri)

    process_contact_import_job(
        job_id=job_id,
        storage=storage,
        session_factory=session_factory,
    )

    session = session_factory()
    try:
        job = session.get(ContactImportJob, job_id)
        assert job is not None
        assert job.status == ContactImportStatusEnum.completed
        assert job.total_rows == 1
        assert job.processed_rows == 1
        assert job.error_rows == 0
        assert job.error_report_uri is None

        contacts = session.query(Contact).filter(Contact.org_id == organization_id).all()
        assert len(contacts) == 1
        assert contacts[0].email == "john@example.com"
    finally:
        session.close()


def test_process_contact_import_failure(tmp_path, session_factory, organization_id):
    storage = TemporaryObjectStorage(base_path=tmp_path / "storage")
    csv_content = "full_name,email,phone\nInvalid User,,\n"
    input_uri = storage.store_bytes(
        csv_content.encode("utf-8"),
        prefix="contact-imports",
        suffix=".csv",
    )

    job_id = _create_job(session_factory, organization_id, input_uri)

    process_contact_import_job(
        job_id=job_id,
        storage=storage,
        session_factory=session_factory,
    )

    session = session_factory()
    try:
        job = session.get(ContactImportJob, job_id)
        assert job is not None
        assert job.status == ContactImportStatusEnum.failed
        assert job.total_rows == 1
        assert job.processed_rows == 0
        assert job.error_rows == 1
        assert job.error_report_uri is not None

        error_report = Path(job.error_report_uri).read_text(encoding="utf-8")
        assert "email or phone must be provided" in error_report

        contacts = session.query(Contact).filter(Contact.org_id == organization_id).all()
        assert contacts == []
    finally:
        session.close()
