import sys
from datetime import datetime
from pathlib import Path
import uuid

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.providers import ProviderCreate, ProviderResponse  # noqa: E402
from app.api.rules import RuleCreate  # noqa: E402
from app.api.rates import RateResponse  # noqa: E402


def test_provider_create_metadata_is_isolated():
    first = ProviderCreate(name="first")
    first.metadata["foo"] = "bar"

    second = ProviderCreate(name="second")

    assert "foo" not in second.metadata


def test_provider_response_accepts_configured_flags():
    payload = {
        "id": str(uuid.uuid4()),
        "name": "demo",
        "type": "whatsapp",
        "status": "active",
        "is_configured": False,
        "has_credentials": False,
    }

    response = ProviderResponse(**payload)
    assert response.is_configured is False
    assert response.has_credentials is False


def test_rule_create_parses_actions_model():
    provider_id = uuid.uuid4()

    rule = RuleCreate(
        name="Route",
        is_enabled=True,
        conditions=[{"type": "country", "values": ["BR"]}],
        actions={
            "primary_provider": str(provider_id),
            "fallback_chain": [],
            "channel": "WhatsApp",
        },
        priority=10,
    )

    assert rule.actions.primary_provider == provider_id
    assert rule.actions.channel == "whatsapp"


@pytest.mark.parametrize("template_name", [None, "promo"])
def test_rate_response_allows_optional_template(template_name):
    rate = RateResponse(
        id=str(uuid.uuid4()),
        provider_id=str(uuid.uuid4()),
        provider_name="demo-provider",
        effective_from=datetime.utcnow(),
        country_iso="BR",
        category="MARKETING",
        template_name=template_name,
        unit_cost_minor=100,
        currency="USD",
    )

    assert rate.template_name == template_name
