"""
Rate limiting configuration using slowapi.
Uses Redis as storage backend when available for shared state across workers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


def create_limiter(redis_url: str = "redis://localhost:6379/0") -> Limiter:
    """Create a slowapi Limiter with Redis or in-memory storage."""
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        storage_uri = redis_url
    except Exception:
        storage_uri = "memory://"

    return Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],
        storage_uri=storage_uri,
    )
