import sys
from pathlib import Path

import fakeredis

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.circuit_breaker import CircuitBreakerStore  # noqa: E402


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._current = start

    def __call__(self) -> float:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current += seconds


def test_circuit_breaker_state_transitions():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    clock = _FakeClock()
    store = CircuitBreakerStore(
        redis_client,
        threshold=2,
        cooldown_seconds=10,
        time_provider=clock,
    )

    provider_id = "provider-1"

    state = store.get_state(provider_id)
    assert state.state == "closed"
    assert state.failure_count == 0

    state = store.mark_failure(provider_id)
    assert state.state == "closed"
    assert state.failure_count == 1

    state = store.mark_failure(provider_id)
    assert state.state == "open"
    assert state.failure_count >= 2
    assert state.is_blocked()

    clock.advance(10)
    state = store.get_state(provider_id)
    assert state.state == "half-open"
    assert state.is_blocked()

    state = store.mark_failure(provider_id)
    assert state.state == "open"
    assert state.failure_count >= 2

    state = store.mark_success(provider_id)
    assert state.state == "closed"
    assert state.failure_count == 0


def test_circuit_breaker_counts_by_state():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    clock = _FakeClock()
    store = CircuitBreakerStore(
        redis_client,
        threshold=1,
        cooldown_seconds=0,
        time_provider=clock,
    )

    store.mark_failure("a")  # opens immediately due to threshold 1
    store.mark_success("b")

    counts = store.count_by_state()
    assert counts["open"] == 0
    assert counts["half-open"] == 1
    assert counts["closed"] >= 1
