"""A tiny in-memory TTL cache.

LESSON: every upstream call costs latency and risks a failure. Site data barely changes,
so we remember answers per location. The cache lives in this process only: it is lost on
restart and not shared between workers, which is fine for a cost-saving layer (it is never
the source of truth). There is no `await` inside, so one event loop can't interleave
half-finished writes.
"""
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_s: int, max_entries: int) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._data: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        expires_at, value = hit
        if expires_at < time.monotonic():
            del self._data[key]
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        if len(self._data) >= self.max_entries:
            # Dicts keep insertion order, so the first key is the oldest entry.
            self._data.pop(next(iter(self._data)))
        self._data[key] = (time.monotonic() + self.ttl_s, value)
