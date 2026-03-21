from __future__ import annotations

import time

from mcp_bespoke_server.idempotency import IdempotencyCache


def test_idempotency_returns_cached_value() -> None:
    cache = IdempotencyCache[str](ttl_seconds=60)
    cache.put("k1", "value")
    assert cache.get("k1") == "value"


def test_idempotency_expires() -> None:
    cache = IdempotencyCache[str](ttl_seconds=0)
    cache.put("k1", "value")
    time.sleep(0.01)
    assert cache.get("k1") is None

