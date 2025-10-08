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
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    ContactSegment,
    ContactSegmentMembership,
    ContactStatusEnum,
    OptInStatusEnum,
    Organization,
)
from app.services.contacts.repository import ContactRepository  # noqa: E402


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


def _create_org(session):
    org = Organization(id=uuid.uuid4(), name="Acme")
    session.add(org)
    session.commit()
    return org


def test_create_get_update_and_delete_contact(session):
    org = _create_org(session)
    repo = ContactRepository(session)

    contact = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        email="pilot@example.com",
        full_name="Pilot Contact",
    )

    fetched = repo.get_contact(org_id=org.id, contact_id=contact.id)
    assert fetched is not None
    assert fetched.email == "pilot@example.com"

    updated = repo.update_contact(
        org_id=org.id,
        contact_id=contact.id,
        first_name="Pilot",
        last_name="User",
    )

    assert updated.first_name == "Pilot"
    assert updated.last_name == "User"

    deleted = repo.delete_contact(org_id=org.id, contact_id=contact.id)
    assert deleted is True
    assert repo.get_contact(org_id=org.id, contact_id=contact.id) is None


def test_list_contacts_filters_by_segment(session):
    org = _create_org(session)
    repo = ContactRepository(session)

    vip_segment = ContactSegment(
        id=uuid.uuid4(),
        org_id=org.id,
        slug="vip",
        name="VIP",
    )
    session.add(vip_segment)
    session.commit()

    contact_vip = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        email="vip@example.com",
        full_name="VIP Customer",
    )
    contact_regular = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        email="user@example.com",
        full_name="User",
    )

    membership = ContactSegmentMembership(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=contact_vip.id,
        segment_id=vip_segment.id,
        membership_origin="import",
        valid_from=datetime.now(timezone.utc),
    )

    session.add(membership)
    session.commit()

    results = repo.list_contacts(org_id=org.id, segment_slugs=["vip"])
    assert {contact.id for contact in results} == {contact_vip.id}

    results_by_id = repo.list_contacts(org_id=org.id, segment_ids=[vip_segment.id])
    assert {contact.id for contact in results_by_id} == {contact_vip.id}

    results_empty = repo.list_contacts(org_id=org.id, segment_slugs=["nonexistent"])
    assert results_empty == []

    # ensure regular contact remains accessible without filters
    all_contacts = repo.list_contacts(org_id=org.id)
    assert {contact.id for contact in all_contacts} == {
        contact_vip.id,
        contact_regular.id,
    }


def test_list_contacts_filters_by_channel_and_status(session):
    org = _create_org(session)
    repo = ContactRepository(session)

    granted_contact = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        phone="+5511999999999",
        status=ContactStatusEnum.active,
    )
    revoked_contact = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        phone="+5511888888888",
        status=ContactStatusEnum.active,
    )

    opt_in_granted = ContactChannelOptIn(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=granted_contact.id,
        channel="whatsapp",
        channel_address=granted_contact.phone,
        status=OptInStatusEnum.granted,
        version=1,
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    opt_in_revoked = ContactChannelOptIn(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=revoked_contact.id,
        channel="whatsapp",
        channel_address=revoked_contact.phone,
        status=OptInStatusEnum.revoked,
        version=1,
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc) - timedelta(days=2),
    )

    session.add_all([opt_in_granted, opt_in_revoked])
    session.commit()

    only_granted = repo.list_contacts(
        org_id=org.id,
        channel="whatsapp",
        channel_status=OptInStatusEnum.granted,
    )

    assert {contact.id for contact in only_granted} == {granted_contact.id}

    any_status = repo.list_contacts(org_id=org.id, channel="whatsapp")
    assert {contact.id for contact in any_status} == {
        granted_contact.id,
        revoked_contact.id,
    }

    by_address = repo.list_contacts(
        org_id=org.id,
        channel="whatsapp",
        channel_address=granted_contact.phone,
    )

    assert {contact.id for contact in by_address} == {granted_contact.id}

