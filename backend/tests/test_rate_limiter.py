import sys
import time
from pathlib import Path

import fakeredis
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.rate_limiter import RateLimitExceeded, RateLimiter


def test_rate_limiter_allows_within_limit():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    limiter = RateLimiter(client, key_prefix="test")

    status = limiter.hit("messages", "org-1", limit=2, ttl_seconds=30)
    assert status.remaining == 1

    status = limiter.hit("messages", "org-1", limit=2, ttl_seconds=30)
    assert status.remaining == 0


def test_rate_limiter_blocks_after_limit():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    limiter = RateLimiter(client, key_prefix="test")

    limiter.hit("messages", "org-1", limit=1, ttl_seconds=15)

    with pytest.raises(RateLimitExceeded) as exc:
        limiter.hit("messages", "org-1", limit=1, ttl_seconds=15)

    assert exc.value.retry_after <= 15
    assert exc.value.retry_after >= 0


def test_rate_limiter_resets_after_ttl_expiry():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    limiter = RateLimiter(client, key_prefix="test")

    limiter.hit("messages", "org-1", limit=1, ttl_seconds=1)

    with pytest.raises(RateLimitExceeded):
        limiter.hit("messages", "org-1", limit=1, ttl_seconds=1)

    time.sleep(1.1)

    status = limiter.hit("messages", "org-1", limit=1, ttl_seconds=1)
    assert status.remaining == 0


def test_rate_limiter_isolated_by_identifier():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    limiter = RateLimiter(client, key_prefix="test")

    limiter.hit("messages", "org-1", limit=1, ttl_seconds=30)

    with pytest.raises(RateLimitExceeded):
        limiter.hit("messages", "org-1", limit=1, ttl_seconds=30)

    # Different identifier should still have full quota
    status_other = limiter.hit("messages", "org-2", limit=1, ttl_seconds=30)
    assert status_other.remaining == 0
