import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes.contacts import ContactResponse, _serialize_contact  # noqa: E402
from app.api.routes.contact_segments import (  # noqa: E402
    SegmentMembershipResponse,
    SegmentPolicyResponse,
    _serialize_membership,
    _serialize_policy,
    _serialize_segment,
)
from pydantic import ValidationError
from app.models.models import (  # noqa: E402
    Contact,
    ContactSegment,
    ContactSegmentMembership,
    ContactSegmentPolicy,
    ContactStatusEnum,
)


@pytest.mark.parametrize(
    "status_value,expected",
    [
        (None, ContactStatusEnum.active),
        ("inactive", ContactStatusEnum.inactive),
        (ContactStatusEnum.archived, ContactStatusEnum.archived),
    ],
)
def test_serialize_contact_coerces_missing_status(status_value, expected):
    contact = Contact(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=status_value,
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 16, tzinfo=timezone.utc),
    )

    serialized = _serialize_contact(contact)

    assert serialized.status == expected


def test_serialize_contact_discards_invalid_email_and_strings():
    contact = Contact(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        full_name={"unexpected": "value"},
        email="invalid-email",
        phone=12345,
        created_at=datetime(2024, 3, 10, tzinfo=timezone.utc),
        updated_at=datetime(2024, 3, 11, tzinfo=timezone.utc),
    )

    serialized = _serialize_contact(contact)

    assert serialized.email is None
    assert serialized.full_name is None
    assert serialized.phone is None


def test_serialize_segment_recovers_missing_slug_and_name():
    segment_id = uuid.uuid4()
    segment = ContactSegment(
        id=segment_id,
        org_id=uuid.uuid4(),
        slug=None,
        name=None,
        created_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 21, tzinfo=timezone.utc),
    )

    serialized = _serialize_segment(segment)

    assert serialized.slug == f"segment-{segment_id}"
    assert serialized.name == serialized.slug


def test_serialize_membership_defaults_origin_label():
    membership = ContactSegmentMembership(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        segment_id=uuid.uuid4(),
        membership_origin=None,
        valid_from=None,
        source=None,
        created_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )

    serialized = _serialize_membership(membership)

    assert isinstance(serialized, SegmentMembershipResponse)
    assert serialized.membership_origin == "legacy"
    assert serialized.valid_from.tzinfo is not None


def test_serialize_contact_falls_back_on_validation_error(monkeypatch):
    contact = Contact(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=ContactStatusEnum.active,
        created_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 4, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(ValidationError) as captured:
        ContactResponse.model_validate({})

    def _raise_validation_error(cls, value, *args, **kwargs):
        raise captured.value

    monkeypatch.setattr(
        ContactResponse,
        "model_validate",
        classmethod(_raise_validation_error),
    )

    serialized = _serialize_contact(contact)

    assert isinstance(serialized, ContactResponse)
    assert serialized.id == contact.id
    assert serialized.status == ContactStatusEnum.active


def test_serialize_policy_with_invalid_payload_returns_defaults():
    policy = ContactSegmentPolicy(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        segment_id=uuid.uuid4(),
        limits={"max_daily_messages": "invalid"},
        opt_out={"channels": "wrong-type", "enforce": "nope"},
    )

    serialized = _serialize_policy(policy)

    assert isinstance(serialized, SegmentPolicyResponse)
    assert serialized.limits.max_daily_messages is None
    assert serialized.opt_out.channels == []
