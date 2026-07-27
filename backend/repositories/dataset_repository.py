"""
Dataset repository — wraps PersistenceLayer dataset cache.
"""

from typing import Dict, Optional

from cache.redis_client import RedisClient
from graph_engine.persistence import PersistenceLayer
from repositories.cache_keys import ALERTS_CACHE_KEY, DATASET_CACHE_KEY


class DatasetRepository:
    """Data access for the synthetic/cached dataset."""

    def __init__(
        self,
        persistence: PersistenceLayer,
        redis_client: Optional[RedisClient] = None,
    ):
        self._persistence = persistence
        self._redis = redis_client

    def get(self) -> Optional[Dict]:
        """Return shared Redis state, with process memory as a fallback."""
        if self._redis is not None:
            shared = self._redis.get(DATASET_CACHE_KEY)
            if shared is not None:
                return shared
        return self._persistence.get_dataset()

    def set(self, dataset: Dict) -> None:
        """Store dataset in process memory and shared Redis without expiry."""
        self._persistence.set_dataset(dataset)
        if self._redis is not None:
            self._redis.set(DATASET_CACHE_KEY, dataset, ttl=None)

    def clear(self) -> None:
        """Clear dataset and alert state across workers."""
        self._persistence.clear()
        if self._redis is not None:
            self._redis.delete(DATASET_CACHE_KEY)
            self._redis.delete(ALERTS_CACHE_KEY)
