import sys
import uuid
from datetime import datetime, timedelta, timezone
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
    Contact,
    Conversation,
    ConversationStatusEnum,
    Organization,
    QueueEntry,
    QueueStatusEnum,
    SlaSnapshot,
)
from app.services.conversations import (  # noqa: E402
    ConversationLifecycleService,
    ConversationMetricsService,
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


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_handle_inbound_creates_conversation_and_queue(session):
    org = _create_org(session)
    lifecycle = ConversationLifecycleService(session)

    occurred_at = datetime(2024, 1, 5, 12, 30, tzinfo=timezone.utc)

    conversation = lifecycle.handle_inbound(
        org_id=org.id,
        channel="whatsapp",
        channel_address="+5511999990000",
        contact_id=None,
        occurred_at=occurred_at,
    )
    session.commit()

    fetched = session.query(Conversation).filter(Conversation.id == conversation.id).one()
    assert fetched.status is ConversationStatusEnum.waiting
    assert _as_utc(fetched.last_inbound_at) == occurred_at

    queue_entry = (
        session.query(QueueEntry)
        .filter(QueueEntry.conversation_id == conversation.id)
        .one()
    )
    assert queue_entry.status is QueueStatusEnum.open
    assert _as_utc(queue_entry.opened_at) == occurred_at


def test_handle_outbound_records_first_response(session):
    org = _create_org(session)
    contact = Contact(id=uuid.uuid4(), org_id=org.id, phone="+5511988880000")
    session.add(contact)
    session.commit()

    lifecycle = ConversationLifecycleService(session)
    inbound_at = datetime(2024, 1, 6, 9, 0, tzinfo=timezone.utc)
    lifecycle.handle_inbound(
        org_id=org.id,
        channel="sms",
        channel_address=contact.phone,
        contact_id=contact.id,
        occurred_at=inbound_at,
    )

    outbound_at = inbound_at + timedelta(minutes=5)
    conversation = lifecycle.handle_outbound(
        org_id=org.id,
        channel="sms",
        channel_address=contact.phone,
        contact_id=contact.id,
        occurred_at=outbound_at,
    )
    session.commit()

    refreshed = session.query(Conversation).filter_by(id=conversation.id).one()
    assert refreshed.status is ConversationStatusEnum.closed
    assert refreshed.first_response_latency_seconds == 300
    assert _as_utc(refreshed.closed_at) == outbound_at

    queue_entry = (
        session.query(QueueEntry)
        .filter(QueueEntry.conversation_id == conversation.id)
        .one()
    )
    assert queue_entry.status is QueueStatusEnum.closed
    assert queue_entry.first_response_latency_seconds == 300
    assert queue_entry.total_duration_seconds == 300
    assert _as_utc(queue_entry.responded_at) == outbound_at


def test_rebuild_snapshots_aggregates_metrics(session):
    org = _create_org(session)

    opened_at = datetime(2024, 2, 1, 9, 30, tzinfo=timezone.utc)
    responded_at = opened_at + timedelta(minutes=8)
    closed_at = opened_at + timedelta(minutes=20)

    conversation = Conversation(
        org_id=org.id,
        contact_id=None,
        channel="email",
        channel_address="customer@example.com",
        status=ConversationStatusEnum.closed,
        opened_at=opened_at,
        last_inbound_at=opened_at,
        first_response_at=responded_at,
        first_response_latency_seconds=480,
        last_outbound_at=closed_at,
        closed_at=closed_at,
    )
    session.add(conversation)
    session.flush()

    queue_entry = QueueEntry(
        org_id=org.id,
        conversation_id=conversation.id,
        channel="email",
        status=QueueStatusEnum.closed,
        opened_at=opened_at,
        responded_at=responded_at,
        closed_at=closed_at,
        first_response_latency_seconds=480,
        total_duration_seconds=1200,
    )
    session.add(queue_entry)
    session.commit()

    metrics = ConversationMetricsService(session, sla_target_seconds=600)
    since = datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc)
    until = datetime(2024, 2, 2, 0, 0, tzinfo=timezone.utc)
    snapshots = metrics.rebuild_snapshots(org_id=org.id, since=since, until=until)
    session.commit()

    assert len(snapshots) == 1
    snapshot = session.query(SlaSnapshot).filter(SlaSnapshot.org_id == org.id).one()
    assert snapshot.channel == "email"
    assert snapshot.conversations_opened == 1
    assert snapshot.conversations_closed == 1
    assert snapshot.first_response_avg_seconds == 480
    assert snapshot.first_response_within_target == 1
    assert snapshot.backlog_open == 1
    assert snapshot.backlog_closed == 1
    assert snapshot.backlog_pending == 0
