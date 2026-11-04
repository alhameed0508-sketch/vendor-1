"""Decision log: recent decisions in memory, live counters, and an optional PostgreSQL sink.

Per docs/SYSTEM_DESIGN.md (D02): every decision is counted, the recent ones are kept in memory for the
live feed, and only non-approved decisions are written to PostgreSQL in full. The sink is write-behind
(a queue flushed every 100 ms), so the database never sits on the payment's path.
"""

from __future__ import annotations

import logging
import queue
import statistics
import threading
from collections import Counter, OrderedDict, deque
from datetime import datetime
from typing import Dict, List, Optional

from intelligence.contracts import APPROVE, ENGINES, REVIEW, STEP_UP, Decision, utc_now

logger = logging.getLogger(__name__)

CONFIRMED_FRAUD, FALSE_ALERT = "CONFIRMED_FRAUD", "FALSE_ALERT"
OUTCOMES = (CONFIRMED_FRAUD, FALSE_ALERT)
ENGINE_ACTIVE_AT = 0.4


class DecisionStore:
    def __init__(self, max_decisions: int = 20_000, sink: Optional["PgDecisionSink"] = None):
        self._decisions: "OrderedDict[str, Decision]" = OrderedDict()
        self._by_txn: Dict[str, str] = {}
        self._max = max_decisions
        self._lock = threading.Lock()
        self._latency = deque(maxlen=5000)
        self._bands: Counter = Counter()
        self._by_source: Dict[str, Counter] = {}
        self._engine_active: Counter = Counter()
        self._reason_codes: Counter = Counter()
        self._histogram = [0] * 10
        self._outcomes: Counter = Counter()
        self._labelled: Counter = Counter()  # synthetic events only
        self._hourly: "OrderedDict[str, Counter]" = OrderedDict()
        self._log: deque = deque(maxlen=max_decisions)  # (sequence, decision) for live tailing
        self._seq = 0
        self._sink = sink

    # ----------------------------------------------------------------- writes
    def put(self, d: Decision) -> None:
        with self._lock:
            self._decisions[d.decision_id] = d
            if d.committed:  # what-ifs never stand in for the real payment
                self._by_txn[d.txn_id] = d.decision_id
            self._seq += 1
            self._log.append((self._seq, d))
            while len(self._decisions) > self._max:
                old_id, old = self._decisions.popitem(last=False)
                if self._by_txn.get(old.txn_id) == old_id:
                    del self._by_txn[old.txn_id]
            self._latency.append(d.latency_ms)
            self._bands[d.band] += 1
            self._by_source.setdefault(d.source, Counter())[d.band] += 1
            for engine, score in d.engines.items():
                if score >= ENGINE_ACTIVE_AT:
                    self._engine_active[engine] += 1
            for r in d.reasons:
                if r.get("kind") != "familiarity":
                    self._reason_codes[r["code"]] += 1
            self._histogram[min(9, d.score // 10)] += 1
            hour = d.decided_at[:13]
            self._hourly.setdefault(hour, Counter())[d.band] += 1
            while len(self._hourly) > 48:
                self._hourly.popitem(last=False)
            if d.label in ("fraud", "genuine"):
                interrupted = d.band != APPROVE
                self._labelled[f"{d.label}_total"] += 1
                self._labelled[f"{d.label}_interrupted"] += int(interrupted)
                self._labelled[f"{d.label}_review"] += int(d.band == REVIEW)
                self._labelled[f"{d.label}_step_up"] += int(d.band == STEP_UP)
        if self._sink is not None and d.band != APPROVE:
            self._sink.enqueue(d)

    def set_outcome(self, decision_id: str, outcome: str, note: str, by: str) -> Optional[Decision]:
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        with self._lock:
            d = self._decisions.get(decision_id)
            if d is None:
                return None
            if d.outcome:
                self._outcomes[d.outcome] -= 1
            d.outcome, d.outcome_note, d.outcome_by = outcome, note[:500], by
            d.outcome_at = utc_now().isoformat()
            self._outcomes[outcome] += 1
        if self._sink is not None:
            self._sink.enqueue(d)
        return d

    # ------------------------------------------------------------------ reads
    def get(self, decision_id: str) -> Optional[Decision]:
        with self._lock:
            return self._decisions.get(decision_id)

    def by_txn(self, txn_id: str) -> Optional[Decision]:
        with self._lock:
            did = self._by_txn.get(txn_id)
            return self._decisions.get(did) if did else None

    @property
    def sequence(self) -> int:
        return self._seq

    def since(self, after: int, limit: int = 100, source: Optional[str] = None) -> List[tuple]:
        """Decisions stored after sequence number ``after`` (oldest first), for live tailing."""
        with self._lock:
            items = [(s, d) for s, d in self._log if s > after and (source is None or d.source == source)]
        return items[:limit]

    def recent(
        self, limit: int = 50, band: Optional[str] = None, min_score: int = 0, source: Optional[str] = None
    ) -> List[Decision]:
        with self._lock:
            items = list(reversed(self._decisions.values()))
        out = []
        for d in items:
            if band and d.band != band:
                continue
            if d.score < min_score or (source and d.source != source):
                continue
            out.append(d)
            if len(out) >= limit:
                break
        return out

    def metrics(self) -> Dict:
        with self._lock:
            lat = sorted(self._latency)
            total = sum(self._bands.values())
            lab = dict(self._labelled)
            outcomes = dict(self._outcomes)
            data = {
                "decisions": total,
                "bands": {b: self._bands.get(b, 0) for b in (APPROVE, STEP_UP, REVIEW)},
                "by_source": {s: dict(c) for s, c in self._by_source.items()},
                "engine_active": {e: self._engine_active.get(e, 0) for e in ENGINES},
                "top_reasons": self._reason_codes.most_common(10),
                "score_histogram": list(self._histogram),
                "hourly": [{"hour": h, **dict(c)} for h, c in self._hourly.items()],
                "latency_ms": {
                    "p50": round(statistics.median(lat), 2) if lat else None,
                    "p95": round(lat[int(0.95 * (len(lat) - 1))], 2) if lat else None,
                    "samples": len(lat),
                },
                "outcomes": outcomes,
            }
        reviewed = outcomes.get(CONFIRMED_FRAUD, 0) + outcomes.get(FALSE_ALERT, 0)
        data["feedback"] = {
            "with_outcome": reviewed,
            "false_alert_share": round(outcomes.get(FALSE_ALERT, 0) / reviewed, 4) if reviewed else None,
            "note": "from investigators' outcomes on decisions they reviewed",
        }
        g, f = lab.get("genuine_total", 0), lab.get("fraud_total", 0)
        review_hits = lab.get("fraud_review", 0) + lab.get("genuine_review", 0)
        data["synthetic_labelled"] = {
            "genuine_payments": g,
            "fraud_payments": f,
            "genuine_interrupted_rate": round(lab.get("genuine_interrupted", 0) / g, 4) if g else None,
            "genuine_review_rate": round(lab.get("genuine_review", 0) / g, 4) if g else None,
            "fraud_caught_rate": round(lab.get("fraud_interrupted", 0) / f, 4) if f else None,
            "review_precision": round(lab.get("fraud_review", 0) / review_hits, 4) if review_hits else None,
            "note": "synthetic events only: labels come from the simulator and are never used for scoring",
        }
        return data


class PgDecisionSink:
    """Write-behind persistence of non-approved decisions and outcomes (PostgreSQL in production)."""

    def __init__(self, engine, flush_seconds: float = 0.1, max_queue: int = 50_000):
        from backend.infra.database.postgres import risk_decisions_table  # noqa: F401 - table must exist

        self._engine = engine
        self._queue: "queue.Queue[Decision]" = queue.Queue(maxsize=max_queue)
        self._flush_seconds = flush_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="risk-decision-sink")
        self._thread.start()

    def enqueue(self, d: Decision) -> None:
        try:
            self._queue.put_nowait(d)
        except queue.Full:
            logger.warning("risk decision sink queue full; decision %s kept in memory only", d.decision_id)

    def _run(self) -> None:
        while not self._stop.is_set():
            batch = []
            try:
                batch.append(self._queue.get(timeout=self._flush_seconds))
                while len(batch) < 500:
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                pass
            if batch:
                self.write(batch)

    def write(self, batch: List[Decision]) -> None:
        from backend.infra.database.postgres import risk_decisions_table as t

        latest = {d.decision_id: d for d in batch}
        try:
            with self._engine.begin() as conn:
                for d in latest.values():
                    row = {
                        "decision_id": d.decision_id,
                        "txn_id": d.txn_id,
                        "customer_id": d.customer_id,
                        "beneficiary_id": d.beneficiary_id,
                        "amount": d.amount,
                        "score": d.score,
                        "band": d.band,
                        "confidence": d.confidence,
                        "engines": d.engines,
                        "reasons": d.reasons,
                        "explanation": d.explanation,
                        "source": d.source,
                        "model_version": d.model_version,
                        "event_time": d.event_time,
                        "decided_at": datetime.fromisoformat(d.decided_at),
                        "outcome": d.outcome,
                        "outcome_note": d.outcome_note,
                        "outcome_by": d.outcome_by,
                    }
                    updated = conn.execute(
                        t.update()
                        .where(t.c.decision_id == d.decision_id)
                        .values(outcome=d.outcome, outcome_note=d.outcome_note, outcome_by=d.outcome_by)
                    ).rowcount
                    if not updated:
                        conn.execute(t.insert().values(**row))
        except Exception as exc:  # noqa: BLE001 - persistence must never break scoring
            logger.error("risk decision sink write failed (%d decisions): %s", len(latest), exc)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
