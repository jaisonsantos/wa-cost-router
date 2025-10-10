import sys
import uuid
from datetime import datetime, timezone
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
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


from app.core.database import Base  # noqa: E402
from app.models.models import (  # noqa: E402
    ContactChannelOptIn,
    ContactStatusEnum,
    OptInStatusEnum,
    Organization,
)
from app.services.contacts.repository import ContactRepository  # noqa: E402
from app.services.routing.preferences import (  # noqa: E402
    ContactPreferenceResolver,
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


def _create_org(session):
    org = Organization(id=uuid.uuid4(), name="Acme")
    session.add(org)
    session.commit()
    return org


def test_resolver_loads_preferences_for_phone_channels(session):
    org = _create_org(session)
    repo = ContactRepository(session)
    resolver = ContactPreferenceResolver(session, org.id)

    contact = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        phone="+5511999999999",
        status=ContactStatusEnum.active,
    )

    opt_in_whatsapp = ContactChannelOptIn(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=contact.id,
        channel="whatsapp",
        channel_address="+5511999999999",
        status=OptInStatusEnum.granted,
        version=1,
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc),
    )

    opt_in_sms = ContactChannelOptIn(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=contact.id,
        channel="sms",
        channel_address="+5511999999999",
        status=OptInStatusEnum.granted,
        version=1,
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc),
    )

    session.add_all([opt_in_whatsapp, opt_in_sms])
    session.commit()

    preferences = resolver.load(channel="whatsapp", channel_address="+55 11 99999-9999")

    assert preferences.contact_exists is True
    assert preferences.contact_id == contact.id
    assert preferences.normalized_address == "5511999999999"
    assert preferences.is_channel_allowed("whatsapp", "+5511999999999") is True
    assert preferences.is_channel_allowed("sms", "+5511999999999") is True
    assert preferences.has_allowed_channels_for("+5511999999999") is True


def test_resolver_loads_preferences_for_email_channel(session):
    org = _create_org(session)
    repo = ContactRepository(session)
    resolver = ContactPreferenceResolver(session, org.id)

    contact = repo.create_contact(
        id=uuid.uuid4(),
        org_id=org.id,
        email="User@Example.com",
        status=ContactStatusEnum.active,
    )

    opt_in_email = ContactChannelOptIn(
        id=uuid.uuid4(),
        org_id=org.id,
        contact_id=contact.id,
        channel="email",
        channel_address="User@Example.com",
        status=OptInStatusEnum.granted,
        version=1,
        legal_basis="consent",
        captured_at=datetime.now(timezone.utc),
    )

    session.add(opt_in_email)
    session.commit()

    preferences = resolver.load(channel="email", channel_address="user@example.COM")

    assert preferences.contact_exists is True
    assert preferences.contact_id == contact.id
    assert preferences.normalized_address == "user@example.com"
    assert preferences.is_channel_allowed("email", "USER@example.com") is True
    assert preferences.has_allowed_channels_for("USER@example.com") is True


def test_resolver_returns_placeholder_when_contact_missing(session):
    org = _create_org(session)
    resolver = ContactPreferenceResolver(session, org.id)

    preferences = resolver.load(channel="email", channel_address="missing@example.com")

    assert preferences.contact_exists is False
    assert preferences.normalized_address == "missing@example.com"
    assert preferences.allowed_channels == {}
    assert preferences.has_allowed_channels_for("missing@example.com") is False
