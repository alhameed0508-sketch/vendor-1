"""Live payments from the public Bitcoin mempool, scored as they arrive (see data/adapters/mempool_adapter.py).

Unlike ``DemoReplay`` there are no ground-truth labels, so events carry no mule/genuine counters:
a flag is a lead for a human, never a measured catch. Owns a private ``RealtimeScorer`` so live
traffic never reaches the public scorer's history.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Iterator, Optional

from services.realtime_scorer import RealtimeScorer

from data.adapters.mempool_adapter import MempoolClient, tx_to_payments

POLL_INTERVAL_S = 4.0  # public API: stay polite
MAX_FETCH_PER_POLL = 3
MAX_STREAM_SECONDS = 300.0
MAX_CONSECUTIVE_FAILURES = 3
MAX_SEEN_TXIDS = 5000
SOURCE = "live"


class LiveFeed:
    def __init__(
        self,
        client: Optional[MempoolClient] = None,
        poll_interval: float = POLL_INTERVAL_S,
        max_fetch_per_poll: int = MAX_FETCH_PER_POLL,
        max_seconds: float = MAX_STREAM_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client or MempoolClient()
        self._poll_interval = poll_interval
        self._max_fetch = max_fetch_per_poll
        self._max_seconds = max_seconds
        self._sleep = sleep
        self._clock = clock
        # Real traffic has no ground truth to replay deterministically, so latency wins: rebuild off the hot path.
        self._scorer = RealtimeScorer([], [], background_refresh=True)

    def events(self, limit: Optional[int] = None, rate: float = 0.0) -> Iterator[dict]:
        """Yield one event per scored payment until ``limit`` payments or the time budget. ``rate`` is ignored: real time sets the pace."""
        started = self._clock()
        seen: dict = {}
        accounts: set = set()
        payments = flagged = failures = 0
        inr_per_btc = self._rate_or_fail()
        while (limit is None or payments < limit) and self._clock() - started < self._max_seconds:
            try:
                fresh = [t for t in self._client.recent_txids() if t not in seen][: self._max_fetch]
                failures = 0
            except OSError as exc:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(f"mempool.space unreachable: {exc}") from exc
                fresh = []
            for txid in fresh:
                seen[txid] = None
                if len(seen) > MAX_SEEN_TXIDS:
                    seen.pop(next(iter(seen)))
                observed = datetime.now(timezone.utc).isoformat()
                try:
                    batch = tx_to_payments(self._client.tx(txid), inr_per_btc, observed)
                except OSError:
                    continue
                for payment in batch:
                    if limit is not None and payments >= limit:
                        return
                    result = self._scorer.score_payment(payment, commit=True)
                    accounts |= {payment["from_account"], payment["to_account"]}
                    payments += 1
                    flagged += result.decision == "FLAG"
                    yield {
                        "source": SOURCE,
                        "payment": payment,
                        "decision": result.decision,
                        "case_id": result.case_id,
                        "ring_members": list(result.ring_members),
                        "risk_score": result.risk_score,
                        "latency_ms": result.latency_ms,
                        "reasons": list(result.reasons),
                        "counters": {"payments": payments, "flagged": flagged, "accounts": len(accounts)},
                    }
            self._sleep(self._poll_interval)

    def _rate_or_fail(self) -> float:
        try:
            return self._client.inr_per_btc()
        except OSError as exc:
            raise RuntimeError(f"mempool.space unreachable: {exc}") from exc
