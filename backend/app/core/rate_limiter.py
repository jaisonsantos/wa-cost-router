"""Rate limiting utilities backed by Redis.

The limiter is designed to work with FastAPI dependencies while remaining
decoupled from HTTP semantics. It exposes a simple `hit` method that increments
usage counters and raises `RateLimitExceeded` when the configured threshold is
crossed.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

import redis
from redis import Redis

from app.core.config import settings


class RateLimitExceeded(Exception):
    """Raised when a consumer exhausts the configured quota."""

    def __init__(self, scope: str, identifier: str, limit: int, retry_after: int) -> None:
        self.scope = scope
        self.identifier = identifier
        self.limit = limit
        self.retry_after = max(retry_after, 0)
        message = f"Rate limit exceeded for scope '{scope}' and identifier '{identifier}'"
        super().__init__(message)


@dataclass(frozen=True)
class RateLimitStatus:
    """Represents the state of a rate limit bucket after a successful hit."""

    scope: str
    identifier: str
    limit: int
    remaining: int
    ttl: int


class RateLimiter:
    """Utility that enforces simple fixed-window limits using Redis."""

    _DEFAULT_PREFIX: Final[str] = "rate-limit"

    def __init__(self, client: Redis, *, key_prefix: str | None = None) -> None:
        self._client = client
        self._key_prefix = key_prefix or self._DEFAULT_PREFIX

    def _build_key(self, scope: str, identifier: str) -> str:
        return f"{self._key_prefix}:{scope}:{identifier}"

    def hit(self, scope: str, identifier: str, *, limit: int, ttl_seconds: int) -> RateLimitStatus:
        """Consume a single quota unit for the given scope/identifier.

        Args:
            scope: Logical group (e.g. ``messages_send``).
            identifier: Tenant or user identifier.
            limit: Maximum number of hits allowed during the TTL window.
            ttl_seconds: Window size in seconds.

        Returns:
            RateLimitStatus describing the remaining quota.

        Raises:
            RateLimitExceeded: when the hit would exceed ``limit``.
        """

        if limit <= 0:
            return RateLimitStatus(
                scope=scope,
                identifier=identifier,
                limit=limit,
                remaining=-1,
                ttl=ttl_seconds,
            )

        redis_key = self._build_key(scope, identifier)
        with self._client.pipeline() as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, ttl_seconds, nx=True)
            pipe.ttl(redis_key)
            current_count, _, ttl = pipe.execute()

        remaining = max(0, limit - int(current_count))
        ttl_value = ttl if isinstance(ttl, int) and ttl > 0 else ttl_seconds

        if current_count > limit:
            raise RateLimitExceeded(scope, identifier, limit, ttl_value)

        return RateLimitStatus(
            scope=scope,
            identifier=identifier,
            limit=limit,
            remaining=remaining,
            ttl=ttl_value,
        )


def _create_redis_client() -> Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """Return a cached RateLimiter instance backed by the configured Redis."""

    return RateLimiter(_create_redis_client())


def reset_rate_limiter_cache() -> None:
    """Clear the cached RateLimiter instance (useful for tests)."""

    get_rate_limiter.cache_clear()  # type: ignore[attr-defined]
