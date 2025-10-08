import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
def compile_uuid(element, compiler, **kw):
    return "CHAR(36)"


from app.api.dependencies import get_current_user  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Contact,
    ContactSegmentMembership,
    Organization,
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
    organization = Organization(id=org_id, name="Test Org")
    db_session.add(organization)
    db_session.commit()

    def override_current_user():
        return {
            "user_id": uuid.uuid4(),
            "org_id": org_id,
            "permissions": ["contacts:read", "contacts:write"],
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


def _create_contact(session, org_id, **overrides):
    counter = overrides.pop("counter", uuid.uuid4().hex[:8])
    contact = Contact(
        org_id=org_id,
        full_name=f"Test Contact {counter}",
        email=f"user-{counter}@example.com",
        phone=f"+55119{counter}",
        source="test",
        **overrides,
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def test_contact_segment_crud_and_memberships_flow(client, db_session):
    test_client, org_id = client
    contact_a = _create_contact(db_session, org_id, counter="1001")
    contact_b = _create_contact(db_session, org_id, counter="1002")

    create_response = test_client.post(
        "/contact-segments/",
        json={
            "slug": "vip",
            "name": "VIP Customers",
            "description": "High value contacts",
            "criteria": {"country": ["BR"]},
        },
    )
    assert create_response.status_code == 201
    segment_payload = create_response.json()
    segment_id = uuid.UUID(segment_payload["id"])
    assert segment_payload["slug"] == "vip"

    list_response = test_client.get("/contact-segments/")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["items"][0]["id"] == segment_payload["id"]

    update_response = test_client.patch(
        f"/contact-segments/{segment_id}",
        json={"description": "Atualizado"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Atualizado"

    membership_response = test_client.post(
        f"/contact-segments/{segment_id}/contacts",
        json={
            "contact_ids": [str(contact_a.id), str(contact_b.id)],
            "membership_origin": "campaign",
            "source": "test-suite",
        },
    )
    assert membership_response.status_code == 200
    membership_payload = membership_response.json()
    assert membership_payload["missing_contact_ids"] == []
    assert set(membership_payload["already_associated"]) == set()
    created_ids = {m["contact_id"] for m in membership_payload["created_memberships"]}
    assert created_ids == {str(contact_a.id), str(contact_b.id)}

    repeat_response = test_client.post(
        f"/contact-segments/{segment_id}/contacts",
        json={
            "contact_ids": [str(contact_a.id)],
            "membership_origin": "campaign",
            "source": "test-suite",
        },
    )
    assert repeat_response.status_code == 200
    repeat_payload = repeat_response.json()
    assert repeat_payload["created_memberships"] == []
    assert repeat_payload["missing_contact_ids"] == []
    assert repeat_payload["already_associated"] == [str(contact_a.id)]

    removal_response = test_client.delete(
        f"/contact-segments/{segment_id}/contacts/{contact_a.id}"
    )
    assert removal_response.status_code == 204

    membership = (
        db_session.query(ContactSegmentMembership)
        .filter(
            ContactSegmentMembership.contact_id == contact_a.id,
            ContactSegmentMembership.segment_id == segment_id,
        )
        .order_by(ContactSegmentMembership.valid_from.desc())
        .first()
    )
    assert membership is not None
    assert isinstance(membership.valid_to, datetime)

    policy_response = test_client.put(
        f"/contact-segments/{segment_id}/policy",
        json={
            "limits": {"max_daily_messages": 100, "max_monthly_messages": 1000},
            "opt_out": {"enforce": True, "channels": ["whatsapp"]},
        },
    )
    assert policy_response.status_code == 200
    policy_payload = policy_response.json()
    assert policy_payload["limits"]["max_daily_messages"] == 100
    assert policy_payload["opt_out"]["channels"] == ["whatsapp"]

    segment_response = test_client.get(f"/contact-segments/{segment_id}")
    assert segment_response.status_code == 200
    segment_with_policy = segment_response.json()
    assert segment_with_policy["policy"]["limits"]["max_monthly_messages"] == 1000

    delete_response = test_client.delete(f"/contact-segments/{segment_id}")
    assert delete_response.status_code == 204

    missing_response = test_client.get(f"/contact-segments/{segment_id}")
    assert missing_response.status_code == 404


def test_membership_and_policy_require_valid_segment(client):
    test_client, _ = client
    bogus_segment_id = uuid.uuid4()

    assoc_response = test_client.post(
        f"/contact-segments/{bogus_segment_id}/contacts",
        json={
            "contact_ids": [str(uuid.uuid4())],
            "membership_origin": "campaign",
        },
    )
    assert assoc_response.status_code == 404

    policy_response = test_client.put(
        f"/contact-segments/{bogus_segment_id}/policy",
        json={"limits": {}, "opt_out": {}},
    )
    assert policy_response.status_code == 404
