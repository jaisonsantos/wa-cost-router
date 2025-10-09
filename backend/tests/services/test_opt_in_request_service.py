import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID as PGUUID

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@compiles(PGUUID, "sqlite")
def compile_uuid(element, compiler, **kw):  # pragma: no cover - compile hook
    return "CHAR(36)"


from app.core.database import Base  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactChannelOptIn,
    OptInRequestStatusEnum,
    Organization,
)
from app.services.contacts.opt_in_request_service import (  # noqa: E402
    OptInRequestService,
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
    session: Session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


class StubSender:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def send_opt_in_template(self, *, to_email: str, template_id: str, variables: dict):
        self.calls.append({"to_email": to_email, "template_id": template_id, "variables": variables})
        if not self.responses:
            raise RuntimeError("no more responses configured")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _create_contact(session: Session) -> Contact:
    org = Organization(id=uuid.uuid4(), name="Demo Org")
    session.add(org)
    session.flush()

    contact = Contact(
        org_id=org.id,
        email="person@example.com",
        phone="+5511998765432",
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def test_enqueue_request_creates_and_sends(db_session):
    contact = _create_contact(db_session)
    sender = StubSender([
        {"status": "sent", "message_id": "stub-123", "success": True}
    ])

    service = OptInRequestService(
        db_session,
        email_sender=sender,
        template_id="opt-in-template",
    )

    request = service.enqueue_request(
        org_id=contact.org_id,
        contact_id=contact.id,
        requested_channel="whatsapp",
        requested_address=contact.phone,
    )

    assert request is not None
    assert request.status == OptInRequestStatusEnum.sent
    assert request.attempt_count == 1
    assert request.external_message_id == "stub-123"
    assert sender.calls[0]["to_email"] == "person@example.com"
    assert request.delivery_metadata["attempts"][0]["status"] == "success"


def test_enqueue_request_returns_none_when_contact_has_no_email(db_session):
    contact = _create_contact(db_session)
    contact.email = None
    db_session.commit()

    service = OptInRequestService(db_session)

    request = service.enqueue_request(
        org_id=contact.org_id,
        contact_id=contact.id,
        requested_channel="whatsapp",
        requested_address=contact.phone,
    )

    assert request is None


def test_process_due_requests_retries_after_failure(db_session):
    contact = _create_contact(db_session)
    sender = StubSender([
        {"status": "error", "error": "temporary", "success": False},
        {"status": "sent", "message_id": "final", "success": True},
    ])
    service = OptInRequestService(
        db_session,
        email_sender=sender,
        template_id="opt-in-template",
        retry_minutes=0,
    )

    request = service.enqueue_request(
        org_id=contact.org_id,
        contact_id=contact.id,
        requested_channel="whatsapp",
        requested_address=contact.phone,
    )

    assert request.status == OptInRequestStatusEnum.pending
    assert request.attempt_count == 1
    assert sender.calls[0]["variables"]["requested_channel"] == "whatsapp"

    processed = service.process_due_requests(limit=5)
    assert processed
    refreshed = db_session.get(type(request), request.id)
    assert refreshed.status == OptInRequestStatusEnum.sent
    assert refreshed.attempt_count == 2
    assert refreshed.external_message_id == "final"


def test_confirm_from_webhook_registers_opt_in(db_session):
    contact = _create_contact(db_session)
    sender = StubSender([
        {"status": "sent", "message_id": "stub", "success": True}
    ])
    service = OptInRequestService(
        db_session,
        email_sender=sender,
        template_id="opt-in-template",
    )

    request = service.enqueue_request(
        org_id=contact.org_id,
        contact_id=contact.id,
        requested_channel="whatsapp",
        requested_address=contact.phone,
    )
    assert request.status == OptInRequestStatusEnum.sent

    confirmed = service.confirm_from_webhook(
        org_id=contact.org_id,
        request_id=request.id,
        channel="whatsapp",
        channel_address=contact.phone,
        agent="email-webhook",
        legal_basis="double_opt_in",
        captured_at=datetime.now(timezone.utc),
        metadata={"provider": "mail"},
        request_ip="127.0.0.1",
    )

    assert confirmed.status == OptInRequestStatusEnum.confirmed
    assert confirmed.opt_in_id is not None
    opt_in = db_session.get(ContactChannelOptIn, confirmed.opt_in_id)
    assert opt_in is not None
    assert opt_in.status.value == "granted"
