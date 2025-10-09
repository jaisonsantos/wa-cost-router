"""Circuit breaker persistence backed by Redis.

This module provides a lightweight circuit breaker implementation that keeps
state per provider in Redis. It exposes a small API tailored for the routing
engine and delivery orchestration code:

* ``get_state`` – read the current effective state.
* ``mark_failure`` – record a failed attempt; transitions to ``open`` when the
  configured threshold is reached.
* ``mark_success`` – reset the circuit back to ``closed``.

The state is stored as JSON documents using the ``circuit:{provider_id}``
pattern. Redis is used so the breaker state is shared across API workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import logging
from typing import Callable, Dict, Iterator, Tuple
import time

import redis
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CircuitState:
    """Snapshot of a provider circuit breaker."""

    state: str
    failure_count: int
    opened_at: float | None
    cooldown_until: float | None

    def is_blocked(self) -> bool:
        return self.state in {"open", "half-open"}


class CircuitBreakerStore:
    """Persist circuit breaker states in Redis."""

    _DEFAULT_PREFIX = "circuit"

    def __init__(
        self,
        client: Redis,
        *,
        key_prefix: str | None = None,
        threshold: int | None = None,
        cooldown_seconds: int | None = None,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix or self._DEFAULT_PREFIX
        self._threshold = max(0, threshold if threshold is not None else settings.CIRCUIT_BREAKER_THRESHOLD)
        self._cooldown = max(0, cooldown_seconds if cooldown_seconds is not None else settings.CIRCUIT_BREAKER_COOLDOWN_SECONDS)
        self._time = time_provider or time.time

    def _build_key(self, provider_id: str) -> str:
        return f"{self._key_prefix}:{provider_id}"

    def get_state(self, provider_id: str) -> CircuitState:
        raw = self._load(provider_id)
        opened_at = raw.get("opened_at")
        failure_count = int(raw.get("failure_count", 0))
        raw_state = raw.get("state", "closed")

        cooldown_until: float | None = None
        effective_state = raw_state

        if raw_state == "open" and opened_at is not None and self._cooldown > 0:
            cooldown_until = opened_at + self._cooldown
            if self._time() >= cooldown_until:
                effective_state = "half-open"
        elif raw_state == "open" and opened_at is not None and self._cooldown == 0:
            effective_state = "half-open"

        return CircuitState(
            state=effective_state if effective_state in {"closed", "open", "half-open"} else "closed",
            failure_count=failure_count,
            opened_at=opened_at,
            cooldown_until=cooldown_until,
        )

    def mark_failure(self, provider_id: str) -> CircuitState:
        now = self._time()
        current = self.get_state(provider_id)
        failure_count = current.failure_count + 1

        if current.state == "half-open" or (self._threshold and failure_count >= self._threshold):
            data = {
                "state": "open",
                "failure_count": max(self._threshold, failure_count),
                "opened_at": now,
            }
        elif current.state == "open":
            data = {
                "state": "open",
                "failure_count": failure_count,
                "opened_at": current.opened_at or now,
            }
        else:
            data = {
                "state": "closed",
                "failure_count": failure_count,
                "opened_at": None,
            }

        if self._threshold == 0:
            data["state"] = "closed"

        self._save(provider_id, data)
        return self.get_state(provider_id)

    def mark_success(self, provider_id: str) -> CircuitState:
        data = {
            "state": "closed",
            "failure_count": 0,
            "opened_at": None,
        }
        self._save(provider_id, data)
        return self.get_state(provider_id)

    def reset(self, provider_id: str) -> None:
        self._client.delete(self._build_key(provider_id))

    def reset_all(self) -> None:
        keys = list(self._client.scan_iter(f"{self._key_prefix}:*"))
        if keys:
            self._client.delete(*keys)

    def iter_states(self) -> Iterator[Tuple[str, CircuitState]]:
        for key in self._client.scan_iter(f"{self._key_prefix}:*"):
            provider_id = key.split(":", maxsplit=1)[-1]
            yield provider_id, self.get_state(provider_id)

    def count_by_state(self) -> Dict[str, int]:
        counts = {"closed": 0, "open": 0, "half-open": 0}
        for _, state in self.iter_states():
            if state.state in counts:
                counts[state.state] += 1
        return counts

    def _load(self, provider_id: str) -> Dict[str, object]:
        raw_value = self._client.get(self._build_key(provider_id))
        if not raw_value:
            return {"state": "closed", "failure_count": 0, "opened_at": None}

        try:
            data = json.loads(raw_value)
            if isinstance(data, dict):
                return data
        except (TypeError, ValueError):
            logger.warning("Invalid circuit breaker payload for provider %s", provider_id)
        return {"state": "closed", "failure_count": 0, "opened_at": None}

    def _save(self, provider_id: str, data: Dict[str, object]) -> None:
        try:
            payload = json.dumps(data)
        except (TypeError, ValueError) as exc:
            logger.error("Unable to serialize circuit breaker payload for provider %s: %s", provider_id, exc)
            return
        self._client.set(self._build_key(provider_id), payload)


def _create_client() -> Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@lru_cache(maxsize=1)
def get_circuit_breaker_store() -> CircuitBreakerStore:
    return CircuitBreakerStore(_create_client())


def reset_circuit_breaker_cache() -> None:
    get_circuit_breaker_store.cache_clear()  # type: ignore[attr-defined]
