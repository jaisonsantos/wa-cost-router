import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.messages.delivery import (
    DELIVERY_ATTEMPTS_COUNTER,
    MESSAGES_SEND_COUNTER,
)
from app.metrics import (
    SLA_FIRST_RESPONSE_SECONDS,
    SLA_FIRST_RESPONSE_TARGET_SECONDS,
    SLA_FIRST_RESPONSE_TRACKED_COUNTER,
    SLA_FIRST_RESPONSE_WITHIN_TARGET_COUNTER,
    record_first_response_latency,
)


def test_messages_send_counter_requires_channel_label():
    assert "channel" in MESSAGES_SEND_COUNTER._labelnames

    with pytest.raises(ValueError):
        MESSAGES_SEND_COUNTER.labels(status="ok", provider="demo")

    child = MESSAGES_SEND_COUNTER.labels(
        status="ok", provider="demo", channel="whatsapp"
    )
    # Calling without increment ensures the label is accepted without side effects.
    assert child._value.get() >= 0


def test_delivery_attempts_counter_requires_channel_label():
    assert "channel" in DELIVERY_ATTEMPTS_COUNTER._labelnames

    with pytest.raises(ValueError):
        DELIVERY_ATTEMPTS_COUNTER.labels(
            provider_id="prov-1", provider="demo", outcome="success"
        )

    child = DELIVERY_ATTEMPTS_COUNTER.labels(
        provider_id="prov-1",
        provider="demo",
        outcome="success",
        channel="sms",
    )
    assert child._value.get() >= 0


def test_record_first_response_latency_updates_metrics():
    labels = {"channel": "email"}

    tracked = SLA_FIRST_RESPONSE_TRACKED_COUNTER.labels(**labels)
    within = SLA_FIRST_RESPONSE_WITHIN_TARGET_COUNTER.labels(**labels)
    histogram = SLA_FIRST_RESPONSE_SECONDS.labels(**labels)
    target_gauge = SLA_FIRST_RESPONSE_TARGET_SECONDS.labels(**labels)

    tracked_before = tracked._value.get()
    within_before = within._value.get()
    sum_before = histogram._sum.get()

    record_first_response_latency("email", 120, target_seconds=300)

    assert tracked._value.get() == tracked_before + 1
    assert within._value.get() == within_before + 1
    assert histogram._sum.get() == sum_before + 120
    assert target_gauge._value.get() == 300.0

    # Second observation above the target should not increment the within-target counter
    record_first_response_latency("email", 400, target_seconds=300)

    assert tracked._value.get() == tracked_before + 2
    assert within._value.get() == within_before + 1

    # None latency should be ignored and not raise errors
    record_first_response_latency("email", None, target_seconds=300)

