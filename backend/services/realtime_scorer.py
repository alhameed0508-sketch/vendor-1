"""Per-payment real-time scoring against the account network.

Scores one payment at a time using method B from the evaluation
(`docs/buildx/05-evaluation.md`): the larger of the temporal smurf score and
the Louvain community suspicion. A payment is flagged only when it touches a
suspicious ring of at least ``MIN_RING_SIZE`` accounts AND one endpoint carries
its own evidence (smurf score >= ``ENDPOINT_EVIDENCE_MIN``). The second gate
keeps genuine customers out: a large genuine community can look "suspicious" by
size and density alone, and one unusual payment never opens a case on its own.

The scorer never blocks a payment. ``FLAG`` means "route to a human reviewer".
State is a bounded rolling window held as an immutable tuple; every call
replaces it rather than mutating it.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from models.community_detection.louvain_detector import Community, LouvainClusterDetector
from models.temporal_weighting.smurf_weighting import score_transaction_batch

REQUIRED_FIELDS = ("txn_id", "from_account", "to_account", "amount", "timestamp")
DEFAULT_MAX_WINDOW = 5000
DEFAULT_FLAG_THRESHOLD = 0.50
MIN_RING_SIZE = 3
# Calibrated on seeded synthetic data: 78% of mule accounts vs 1.9% of genuine accounts reach it.
ENDPOINT_EVIDENCE_MIN = 0.30
MAX_REASONS = 6
CASE_ID_PREFIX = "CASE-"
CASE_ID_HEX_LEN = 8


@dataclass(frozen=True)
class PaymentScore:
    txn_id: str
    risk_score: float
    decision: str  # "FLAG" (human review) | "PASS"
    case_id: Optional[str]
    ring_members: Tuple[str, ...]
    reasons: Tuple[str, ...]
    latency_ms: float


def _validate(txn: Mapping) -> None:
    missing = [f for f in REQUIRED_FIELDS if txn.get(f) in (None, "")]
    if missing:
        raise ValueError(f"payment missing required fields: {', '.join(missing)}")
    try:
        float(txn["amount"])
    except (TypeError, ValueError) as exc:
        raise ValueError("payment amount must be numeric") from exc


def _case_id(members: Sequence[str]) -> str:
    digest = hashlib.sha256(min(members).encode()).hexdigest()
    return f"{CASE_ID_PREFIX}{digest[:CASE_ID_HEX_LEN].upper()}"


class RealtimeScorer:
    def __init__(
        self,
        accounts: Sequence[Mapping],
        history: Sequence[Mapping],
        max_window: int = DEFAULT_MAX_WINDOW,
        flag_threshold: float = DEFAULT_FLAG_THRESHOLD,
    ):
        self._accounts: Tuple[Dict, ...] = tuple(dict(a) for a in accounts)
        self._history: Tuple[Dict, ...] = tuple(dict(t) for t in history)[-max_window:]
        self._max_window = max_window
        self._flag_threshold = flag_threshold
        self._lock = threading.Lock()

    @property
    def history_size(self) -> int:
        return len(self._history)

    def score_payment(self, payment: Mapping) -> PaymentScore:
        _validate(payment)
        started = time.perf_counter()
        txn = dict(payment)

        with self._lock:
            window = (*self._history, txn)[-self._max_window :]
            self._history = window
            accounts = self._accounts

        return self._score(txn, list(window), self._with_known_accounts(accounts, window), started)

    @staticmethod
    def _with_known_accounts(accounts: Tuple[Dict, ...], window: Sequence[Mapping]) -> List[Dict]:
        """Add stub entries for accounts seen only in payments (the graph needs a node)."""
        known = {a["account_id"] for a in accounts}
        seen = {acc for t in window for acc in (t["from_account"], t["to_account"])}
        stubs = [{"account_id": acc} for acc in sorted(seen - known)]
        return [*accounts, *stubs]

    def _score(self, txn: Dict, window: List[Dict], accounts: List[Dict], started: float) -> PaymentScore:
        sender, receiver = txn["from_account"], txn["to_account"]
        smurf = score_transaction_batch(window)
        communities = LouvainClusterDetector().detect_clusters(window, accounts)
        ring = self._ring_for(communities, (sender, receiver))

        endpoint_scores = []
        reasons: List[str] = []
        for acc in (sender, receiver):
            score = smurf.get(acc)
            if score is not None:
                endpoint_scores.append(score.smurf_score)
                reasons.extend(f"{acc}: {code}" for code in score.reason_codes)

        evidence = max(endpoint_scores, default=0.0)
        has_evidence = evidence >= ENDPOINT_EVIDENCE_MIN
        ring_support = ring.suspicion_score if ring is not None and has_evidence else 0.0
        if ring_support:
            reasons = [*ring.reason_codes, *reasons]

        risk = round(min(max(evidence, ring_support), 1.0), 4)
        flagged = ring is not None and ring.size >= MIN_RING_SIZE and has_evidence and risk >= self._flag_threshold
        members = tuple(sorted(ring.accounts)) if flagged and ring is not None else ()

        return PaymentScore(
            txn_id=txn["txn_id"],
            risk_score=risk,
            decision="FLAG" if flagged else "PASS",
            case_id=_case_id(members) if flagged else None,
            ring_members=members,
            reasons=tuple(reasons[:MAX_REASONS]) if flagged else (),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    @staticmethod
    def _ring_for(communities: Sequence[Community], endpoints: Sequence[str]) -> Optional[Community]:
        touching = [c for c in communities if any(e in c.accounts for e in endpoints)]
        return max(touching, key=lambda c: c.suspicion_score, default=None)
