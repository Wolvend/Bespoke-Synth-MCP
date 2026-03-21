from __future__ import annotations

import time
from collections import deque
from typing import Any


class TelemetryBuffer:
    def __init__(self, capacity: int = 500) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=capacity)

    def add(self, item: dict[str, Any]) -> None:
        enriched = dict(item)
        enriched.setdefault("ts_ms", int(time.time() * 1000))
        self._items.append(enriched)

    def last(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._items)[-limit:]

