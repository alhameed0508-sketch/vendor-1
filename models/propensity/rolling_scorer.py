"""
Rolling Mule Propensity Scorer
================================
Inspired by Feedzai's continuous per-account risk scoring.
Maintains a rolling propensity score across 5 time windows:
  1h, 6h, 24h, 7d, 30d

Each window tracks velocity, pass-through ratio, and recipient diversity.
External signal boosts from smurf scoring, device trust, semantics, and
behavioral baseline deviation are also factored in.

The score is updated on every new transaction and cached in PropensityStore.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Time window definitions (name, seconds)
WINDOWS: Tuple[Tuple[str, int], ...] = (
    ("1h", 3600),
    ("6h", 6 * 3600),
    ("24h", 24 * 3600),
    ("7d", 7 * 24 * 3600),
    ("30d", 30 * 24 * 3600),
)

# Window weights (recent activity weighted more heavily)
WINDOW_WEIGHTS: Dict[str, float] = {
    "1h": 0.30,
    "6h": 0.25,
    "24h": 0.20,
    "7d": 0.15,
    "30d": 0.10,
}

# External signal boost weights
EXTERNAL_WEIGHTS: Dict[str, float] = {
    "smurf": 0.15,
    "device_trust": 0.10,
    "semantics": 0.05,
    "baseline_deviation": 0.10,
}


@dataclass(frozen=True)
class PropensityRecord:
    account_id: str
    score: float
    window_scores: Tuple[Tuple[str, float], ...]
    signal_breakdown: Tuple[Tuple[str, float], ...]
    updated_at: float


class RollingPropensityScorer:
    """Maintains rolling propensity scores across 5 time windows."""

    def __init__(self, propensity_store=None):
        self._store = propensity_store
        # account_id -> list of (timestamp, amount, recipient, is_incoming)
        self._txn_history: Dict[str, List[Tuple[float, float, str, bool]]] = {}

    def record_transaction(
        self,
        account_id: str,
        amount: float,
        recipient: str,
        timestamp: float = None,
        is_incoming: bool = False,
    ) -> None:
        """Record a transaction for rolling score computation."""
        ts = timestamp or time.time()
        self._txn_history.setdefault(account_id, []).append(
            (ts, amount, recipient, is_incoming)
        )

    def update_score(
        self,
        account_id: str,
        smurf_score: float = 0.0,
        device_trust: float = 0.0,
        semantics_score: float = 0.0,
        baseline_deviation: float = 0.0,
    ) -> PropensityRecord:
        """Recompute propensity score for an account.

        Called after every new transaction or on-demand.
        """
        now = time.time()
        history = self._txn_history.get(account_id, [])

        # Score each time window
        window_scores: List[Tuple[str, float]] = []
        for window_name, window_seconds in WINDOWS:
            cutoff = now - window_seconds
            window_txns = [
                (ts, amt, recip, inc) for ts, amt, recip, inc in history if ts >= cutoff
            ]
            score = self._score_window(window_txns)
            window_scores.append((window_name, round(score, 4)))

        # Weighted blend of window scores
        base_score = sum(WINDOW_WEIGHTS[name] * score for name, score in window_scores)

        # External signal boosts
        external_boost = (
            EXTERNAL_WEIGHTS["smurf"] * smurf_score
            + EXTERNAL_WEIGHTS["device_trust"] * device_trust
            + EXTERNAL_WEIGHTS["semantics"] * semantics_score
            + EXTERNAL_WEIGHTS["baseline_deviation"] * baseline_deviation
        )

        final_score = min(base_score + external_boost, 1.0)
        final_score = round(max(final_score, 0.0), 4)

        signal_breakdown = (
            ("base_window_score", round(base_score, 4)),
            ("smurf_boost", round(EXTERNAL_WEIGHTS["smurf"] * smurf_score, 4)),
            (
                "device_trust_boost",
                round(EXTERNAL_WEIGHTS["device_trust"] * device_trust, 4),
            ),
            (
                "semantics_boost",
                round(EXTERNAL_WEIGHTS["semantics"] * semantics_score, 4),
            ),
            (
                "baseline_boost",
                round(EXTERNAL_WEIGHTS["baseline_deviation"] * baseline_deviation, 4),
            ),
        )

        record = PropensityRecord(
            account_id=account_id,
            score=final_score,
            window_scores=tuple(window_scores),
            signal_breakdown=signal_breakdown,
            updated_at=now,
        )

        # Cache in store if available
        if self._store is not None:
            try:
                from cache.propensity_store import PropensityRecord as StoreRecord

                store_record = StoreRecord(
                    account_id=record.account_id,
                    score=record.score,
                    window_scores=record.window_scores,
                    signal_breakdown=record.signal_breakdown,
                    updated_at=record.updated_at,
                )
                self._store.set(store_record)
            except Exception as exc:
                logger.warning("Failed to cache propensity score: %s", exc)

        return record

    def get_score(self, account_id: str) -> Optional[PropensityRecord]:
        """Get the latest propensity score for an account."""
        if self._store is not None:
            try:
                cached = self._store.get(account_id)
                if cached:
                    return PropensityRecord(
                        account_id=cached.account_id,
                        score=cached.score,
                        window_scores=cached.window_scores,
                        signal_breakdown=cached.signal_breakdown,
                        updated_at=cached.updated_at,
                    )
            except Exception:
                pass
        # Recompute if not cached
        if account_id in self._txn_history:
            return self.update_score(account_id)
        return None

    @staticmethod
    def _score_window(
        txns: List[Tuple[float, float, str, bool]],
    ) -> float:
        """Score a single time window based on velocity, pass-through, and diversity."""
        if not txns:
            return 0.0

        outgoing = [(ts, amt, recip) for ts, amt, recip, inc in txns if not inc]
        incoming = [(ts, amt, recip) for ts, amt, recip, inc in txns if inc]

        # Velocity: number of outgoing transactions (normalized)
        velocity = min(len(outgoing) / 20.0, 1.0)

        # Pass-through ratio: outgoing / incoming amounts
        total_in = sum(amt for _, amt, _ in incoming)
        total_out = sum(amt for _, amt, _ in outgoing)
        if total_in > 0:
            pass_through = min(total_out / total_in, 1.0)
        else:
            pass_through = 0.5 if total_out > 0 else 0.0

        # Recipient diversity (normalized)
        unique_recipients = len(set(recip for _, _, recip in outgoing))
        diversity = min(unique_recipients / 10.0, 1.0)

        # Weighted combination
        score = 0.40 * velocity + 0.35 * pass_through + 0.25 * diversity
        return min(score, 1.0)

    def get_top_risk(self, limit: int = 50) -> List[PropensityRecord]:
        """Return top-risk accounts by propensity score."""
        if self._store is not None:
            try:
                cached = self._store.get_top_risk(limit=limit)
                if cached:
                    return [
                        PropensityRecord(
                            account_id=r.account_id,
                            score=r.score,
                            window_scores=r.window_scores,
                            signal_breakdown=r.signal_breakdown,
                            updated_at=r.updated_at,
                        )
                        for r in cached
                    ]
            except Exception:
                pass

        # Fallback: compute from in-memory history
        records = []
        for acc_id in self._txn_history:
            record = self.update_score(acc_id)
            records.append(record)
        records.sort(key=lambda r: r.score, reverse=True)
        return records[:limit]
