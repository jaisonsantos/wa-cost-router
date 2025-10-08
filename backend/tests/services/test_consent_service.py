import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


from app.core.database import Base  # noqa: E402
from app.models.models import Contact, OptInStatusEnum, Organization  # noqa: E402
from app.services.contacts.consent_service import (  # noqa: E402
    ConsentService,
    ConsentValidationError,
    DuplicateOptInError,
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


def _create_org_and_contact(session):
    org = Organization(id=uuid.uuid4(), name="Acme")
    contact = Contact(
        id=uuid.uuid4(),
        org_id=org.id,
        email="qa@example.com",
        full_name="QA User",
        source="manual",
    )
    session.add_all([org, contact])
    session.commit()
    return org, contact


def test_register_opt_in_updates_version_and_records_evidence(session):
    org, contact = _create_org_and_contact(session)
    service = ConsentService(session)

    initial_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    opt_in = service.register_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address="+5511999999999",
        source="manual",
        agent="qa-analyst",
        legal_basis="consent",
        captured_at=initial_time,
        idempotency_key="initial-opt-in",
        evidence_uri="https://storage.local/optins/1",
    )

    assert opt_in.status == OptInStatusEnum.granted
    assert opt_in.version == 1
    assert opt_in.source_metadata["agent"] == "qa-analyst"
    assert opt_in.source_metadata["channel"] == "whatsapp"
    assert opt_in.source_metadata["idempotency_key"] == "initial-opt-in"

    same = service.register_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address="+5511999999999",
        source="manual",
        agent="qa-analyst",
        legal_basis="consent",
        captured_at=initial_time,
        idempotency_key="initial-opt-in",
    )

    assert same.id == opt_in.id
    assert same.version == 1

    updated_time = initial_time + timedelta(minutes=1)
    updated = service.register_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address="+5511999999999",
        source="manual",
        agent="ops-engineer",
        legal_basis="consent",
        captured_at=updated_time,
        idempotency_key="updated-opt-in",
    )

    assert updated.version == 2
    assert updated.status == OptInStatusEnum.granted
    assert updated.source_metadata["agent"] == "ops-engineer"
    assert updated.source_metadata["idempotency_key"] == "updated-opt-in"
    assert updated.source_metadata["channel"] == "whatsapp"


def test_revoke_opt_in_creates_new_version(session):
    org, contact = _create_org_and_contact(session)
    service = ConsentService(session)

    initial = service.register_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="email",
        channel_address="qa@example.com",
        source="manual",
        agent="qa-analyst",
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=3),
    )

    revoked = service.revoke_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="email",
        channel_address="qa@example.com",
        source="manual",
        agent="compliance-user",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        idempotency_key="revoke-1",
    )

    assert revoked.version == initial.version + 1
    assert revoked.status == OptInStatusEnum.revoked
    assert revoked.source_metadata["action"] == "revoked"
    assert revoked.source_metadata["agent"] == "compliance-user"
    assert revoked.source_metadata["idempotency_key"] == "revoke-1"

    same_revocation = service.revoke_opt_in(
        org_id=org.id,
        contact_id=contact.id,
        channel="email",
        channel_address="qa@example.com",
        source="manual",
        agent="compliance-user",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        idempotency_key="revoke-1",
    )

    assert same_revocation.id == revoked.id

    with pytest.raises(DuplicateOptInError):
        service.revoke_opt_in(
            org_id=org.id,
            contact_id=contact.id,
            channel="email",
            channel_address="qa@example.com",
            source="manual",
            agent="compliance-user",
            captured_at=datetime.now(timezone.utc) - timedelta(seconds=30),
            idempotency_key="revoke-2",
        )


def test_register_opt_in_invalid_source(session):
    org, contact = _create_org_and_contact(session)
    service = ConsentService(session)

    with pytest.raises(ConsentValidationError):
        service.register_opt_in(
            org_id=org.id,
            contact_id=contact.id,
            channel="sms",
            channel_address="+5511888888888",
            source="unauthorized",
            agent="ops",
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
