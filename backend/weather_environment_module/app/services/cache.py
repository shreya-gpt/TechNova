"""
Minimal in-process TTL cache.

For a SIH prototype, an in-memory cache is sufficient and keeps the stack
simple (no extra infrastructure). In production this class's interface
(get/set) could be backed by Redis instead - swap the implementation here
and nothing else in the codebase needs to change.

Example production swap:
    class RedisCache:
        def __init__(self, redis_client): ...
        def get(self, key): return self._client.get(key)
        def set(self, key, value, ttl_seconds): self._client.setex(key, ttl_seconds, value)
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    def __init__(self):
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Process-wide singleton caches per data type, so TTLs can differ.
current_weather_cache = TTLCache()
forecast_cache = TTLCache()
historical_cache = TTLCache()
soil_moisture_cache = TTLCache()
