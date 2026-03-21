from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    expires_at: float
    value: T


class IdempotencyCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, _Entry[T]] = {}

    def get(self, key: str | None) -> T | None:
        if not key:
            return None
        with self._lock:
            self._purge_locked()
            entry = self._store.get(key)
            return None if entry is None else entry.value

    def put(self, key: str | None, value: T) -> None:
        if not key:
            return
        with self._lock:
            self._purge_locked()
            self._store[key] = _Entry(
                expires_at=time.monotonic() + self.ttl_seconds,
                value=value,
            )

    def _purge_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._store.items() if entry.expires_at <= now]
        for key in expired:
            self._store.pop(key, None)

