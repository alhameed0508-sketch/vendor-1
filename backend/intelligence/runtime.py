"""Running the unified engine inside the API: demo traffic and the live public-payments feed.

* ``DemoTraffic`` (demo mode only): warms the shared engine with simulated history in the background, then
  feeds the simulator's later days through it at a steady pace, so the dashboard has a live decision
  stream. Every event is labelled ``source="synthetic"``; it pauses when nobody has looked for a while.
* ``RiskLiveFeed``: real public Bitcoin payments from mempool.space, scored by a *private* engine (its own
  profiles, ring map and store), exactly like the existing ``services/live_feed.py``. Nothing from the
  live feed reaches the shared engine. Each event carries its provenance (provider, URL, observed time).
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Iterator, Optional

from intelligence.decision_store import DecisionStore
from intelligence.engine import UnifiedRiskEngine
from intelligence.mule_network import MuleNetworkIntel
from intelligence.simulator import JourneySimulator, split_by_day

from data.adapters.mempool_adapter import MempoolClient, tx_to_payments

logger = logging.getLogger(__name__)

DEMO_SOURCE = "synthetic"
LIVE_SOURCE = "live"
DEMO_IDLE_PAUSE_SECONDS = 600.0
DEMO_HISTORY_DAYS = 45
DEMO_DAYS = 60

POLL_INTERVAL_S = 4.0  # public API: stay polite
MAX_FETCH_PER_POLL = 3
MAX_STREAM_SECONDS = 300.0
MAX_CONSECUTIVE_FAILURES = 3
MAX_SEEN_TXIDS = 5000


class DemoTraffic:
    """Background synthetic traffic for the shared engine (demo mode only)."""

    def __init__(
        self,
        engine: UnifiedRiskEngine,
        rate: float = 2.0,
        customers: int = 400,
        rings: int = 4,
        seed: int = 7,
        sleep: Callable[[float], None] = time.sleep,
        idle_pause: float = DEMO_IDLE_PAUSE_SECONDS,
    ):
        self.engine = engine
        self.rate = max(0.1, rate)
        self.customers, self.rings, self.seed = customers, rings, seed
        self._sleep = sleep
        self._idle_pause = idle_pause
        self._last_seen = time.monotonic()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.state = "idle"
        self.round = 0
        self.fed = 0
        self.warmed_payments = 0

    def touch(self) -> None:
        """Somebody is looking: make sure traffic is flowing."""
        self._last_seen = time.monotonic()
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(target=self._run, daemon=True, name="risk-demo-traffic")
                self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> Dict:
        return {
            "state": self.state,
            "round": self.round,
            "payments_fed": self.fed,
            "warm_up_payments": self.warmed_payments,
            "rate_per_second": self.rate,
            "source": DEMO_SOURCE,
            "data": "synthetic: simulated customers, mule rings and fraud journeys",
        }

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.round += 1
                sim = JourneySimulator(
                    seed=self.seed + self.round - 1,
                    customers=self.customers,
                    rings=self.rings,
                    run_tag=f"D{self.round}",
                )
                self.state = "warming_up"
                events = sim.run(days=DEMO_DAYS, fraud_from_day=DEMO_HISTORY_DAYS)
                history, live = split_by_day(events, sim.start, DEMO_HISTORY_DAYS)
                self.warmed_payments = self.engine.warm_up([e.event for e in history], sim.accounts())
                self.state = "streaming"
                for e in live:
                    if self._stop.is_set():
                        return
                    while time.monotonic() - self._last_seen > self._idle_pause and not self._stop.is_set():
                        self.state = "paused (no viewers)"
                        self._sleep(1.0)
                    self.state = "streaming"
                    self.engine.assess(e.event, commit=True, source=DEMO_SOURCE, label=e.label)
                    self.fed += 1
                    self._sleep(1.0 / self.rate)
        except Exception:  # noqa: BLE001 - background demo traffic must never take the API down
            logger.exception("risk demo traffic stopped")
            self.state = "stopped (error, see logs)"


class RiskLiveFeed:
    """Real public payments (Bitcoin mempool) through a private unified engine."""

    def __init__(
        self,
        client: Optional[MempoolClient] = None,
        engine: Optional[UnifiedRiskEngine] = None,
        poll_interval: float = POLL_INTERVAL_S,
        max_fetch_per_poll: int = MAX_FETCH_PER_POLL,
        max_seconds: float = MAX_STREAM_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client or MempoolClient()
        self.engine = engine or UnifiedRiskEngine(
            mule=MuleNetworkIntel(background=True), store=DecisionStore(max_decisions=2000)
        )
        self._poll_interval = poll_interval
        self._max_fetch = max_fetch_per_poll
        self._max_seconds = max_seconds
        self._sleep = sleep
        self._clock = clock

    def events(self, limit: Optional[int] = None) -> Iterator[Dict]:
        started = self._clock()
        seen: Dict[str, None] = {}
        payments = interrupted = failures = 0
        try:
            inr_per_btc = self._client.inr_per_btc()
        except OSError as exc:
            raise RuntimeError(f"mempool.space unreachable: {exc}") from exc
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
                    decision = self.engine.assess(payment, commit=True, source=LIVE_SOURCE)
                    payments += 1
                    interrupted += decision.band != "APPROVE"
                    yield {
                        "source": LIVE_SOURCE,
                        "decision": decision.to_dict(full=True),
                        "provenance": {
                            "provider": "mempool.space (public Bitcoin mempool)",
                            "url": f"https://mempool.space/tx/{txid}",
                            "observed_at": observed,
                            "inr_per_btc": inr_per_btc,
                            "note": "Real public payments. No session, device or customer data "
                            "exists for them, so only the mule-network, payee and "
                            "behaviour engines can speak. No ground truth: a hold is a "
                            "lead, not a measured catch.",
                        },
                        "counters": {"payments": payments, "interrupted": interrupted},
                    }
            self._sleep(self._poll_interval)
