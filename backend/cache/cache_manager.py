"""
Two-layer cache: L1 in-memory (OrderedDict LRU + TTL) + L2 Redis.
Read path: L1 -> L2 -> miss (promote to L1 on L2 hit).
Write path: write-through to both layers.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from cache.redis_client import RedisClient


class L1Cache:
    """Thread-safe in-memory LRU cache with TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict = OrderedDict()
        self._expiry: dict = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._store:
                return None
            if time.time() > self._expiry.get(key, 0):
                del self._store[key]
                del self._expiry[key]
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            self._expiry[key] = time.time() + effective_ttl
            while len(self._store) > self._max_size:
                oldest_key, _ = self._store.popitem(last=False)
                self._expiry.pop(oldest_key, None)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._expiry.clear()


class CacheManager:
    """Two-layer cache with L1 in-memory and L2 Redis."""

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        l1_max_size: int = 1000,
        l1_default_ttl: int = 60,
        l2_default_ttl: int = 600,
    ):
        self._l1 = L1Cache(max_size=l1_max_size, default_ttl=l1_default_ttl)
        self._l2 = redis_client
        self._l2_default_ttl = l2_default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Read path: L1 -> L2 -> miss."""
        # L1 check
        value = self._l1.get(key)
        if value is not None:
            return value

        # L2 check (promote to L1 on hit)
        if self._l2 is not None:
            value = self._l2.get(key)
            if value is not None:
                self._l1.set(key, value)
                return value

        return None

    def set(
        self,
        key: str,
        value: Any,
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None,
    ) -> None:
        """Write-through: write to both L1 and L2."""
        self._l1.set(key, value, ttl=l1_ttl)
        if self._l2 is not None:
            effective_l2_ttl = l2_ttl if l2_ttl is not None else self._l2_default_ttl
            self._l2.set(key, value, ttl=effective_l2_ttl)

    def delete(self, key: str) -> None:
        """Delete from both layers."""
        self._l1.delete(key)
        if self._l2 is not None:
            self._l2.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        """Pattern invalidation: clear L1, scan+delete L2."""
        self._l1.clear()
        if self._l2 is not None:
            self._l2.delete_pattern(pattern)
