"""
Redis-backed propensity score store with in-memory fallback.
Stores rolling mule propensity scores per account with 30-day TTL.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

KEY_PREFIX = "mulecatch:propensity:"
DEFAULT_TTL = 30 * 24 * 3600  # 30 days


@dataclass(frozen=True)
class PropensityRecord:
    account_id: str
    score: float
    window_scores: Tuple[Tuple[str, float], ...]  # (window_name, score) pairs
    signal_breakdown: Tuple[Tuple[str, float], ...]  # (signal_name, contribution)
    updated_at: float  # epoch timestamp


class PropensityStore:
    """Redis-backed propensity score store with in-memory fallback."""

    def __init__(self, redis_client=None, ttl: int = DEFAULT_TTL):
        self._redis = redis_client
        self._ttl = ttl
        self._memory: Dict[str, PropensityRecord] = {}
        self._use_redis = False
        if redis_client is not None:
            try:
                redis_client.ping()
                self._use_redis = True
                logger.info("PropensityStore: using Redis backend")
            except Exception:
                logger.info("PropensityStore: Redis unavailable, using in-memory fallback")

    def get(self, account_id: str) -> Optional[PropensityRecord]:
        """Retrieve propensity record for an account."""
        if self._use_redis:
            try:
                import json

                data = self._redis.get(f"{KEY_PREFIX}{account_id}")
                if data:
                    parsed = json.loads(data)
                    return PropensityRecord(
                        account_id=parsed["account_id"],
                        score=parsed["score"],
                        window_scores=tuple(tuple(ws) for ws in parsed["window_scores"]),
                        signal_breakdown=tuple(tuple(sb) for sb in parsed["signal_breakdown"]),
                        updated_at=parsed["updated_at"],
                    )
            except Exception as exc:
                logger.warning("Redis propensity get failed: %s", exc)

        return self._memory.get(account_id)

    def set(self, record: PropensityRecord) -> None:
        """Store propensity record."""
        self._memory[record.account_id] = record

        if self._use_redis:
            try:
                import json

                data = json.dumps(
                    {
                        "account_id": record.account_id,
                        "score": record.score,
                        "window_scores": list(record.window_scores),
                        "signal_breakdown": list(record.signal_breakdown),
                        "updated_at": record.updated_at,
                    }
                )
                self._redis.setex(
                    f"{KEY_PREFIX}{record.account_id}",
                    self._ttl,
                    data,
                )
            except Exception as exc:
                logger.warning("Redis propensity set failed: %s", exc)

    def get_top_risk(self, limit: int = 50) -> List[PropensityRecord]:
        """Return top-risk accounts by propensity score."""
        records = sorted(
            self._memory.values(),
            key=lambda r: r.score,
            reverse=True,
        )
        return records[:limit]
