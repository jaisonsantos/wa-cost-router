import pytest
from datetime import datetime, timezone

from app.services.routing.policies import RoutingPolicyService, RoutingPolicyViolation


def test_policy_blocks_blocked_country():
    service = RoutingPolicyService(quiet_hours=[])

    with pytest.raises(RoutingPolicyViolation) as excinfo:
        service.validate(
            template_category="MARKETING",
            channel="whatsapp",
            country_iso="BR",
            requested_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            template_metadata={"blocked_countries": ["br"]},
        )

    assert excinfo.value.code == "template_blocked_country"


def test_policy_blocks_outside_allowed_hours():
    service = RoutingPolicyService(quiet_hours=[])

    with pytest.raises(RoutingPolicyViolation) as excinfo:
        service.validate(
            template_category="MARKETING",
            channel="whatsapp",
            country_iso="BR",
            requested_at=datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
            template_metadata={"allowed_hours": ["08:00-09:00"]},
        )

    assert excinfo.value.code == "template_outside_allowed_hours"


def test_policy_allows_within_allowed_hours():
    service = RoutingPolicyService(quiet_hours=[])

    service.validate(
        template_category="MARKETING",
        channel="whatsapp",
        country_iso="BR",
        requested_at=datetime(2024, 1, 1, 8, 30, tzinfo=timezone.utc),
        template_metadata={"allowed_hours": ["08:00-09:00"]},
    )
