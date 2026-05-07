"""
Redis connection with connection pooling and graceful fallback.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisClient:
    """Redis wrapper with graceful degradation when unavailable."""

    def __init__(self, url: str = "redis://localhost:6379/0"):
        self._client = None
        self._available = False
        if not HAS_REDIS:
            logger.info("redis package not installed — L2 cache disabled")
            return
        try:
            self._client = redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            self._client.ping()
            self._available = True
            logger.info("Redis connected — L2 cache enabled")
        except Exception as exc:
            logger.info("Redis unavailable (%s) — L2 cache disabled", exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 600) -> bool:
        if not self._available:
            return False
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted."""
        if not self._available:
            return 0
        try:
            count = 0
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    self._client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return 0
