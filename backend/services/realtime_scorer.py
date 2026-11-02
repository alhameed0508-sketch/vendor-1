"""Per-payment real-time scoring against the account network.

Scores one payment at a time using method B from the evaluation
(`docs/buildx/05-evaluation.md`): the larger of the temporal smurf score and
the Louvain community suspicion. A payment is flagged only when it touches a
suspicious ring of at least ``MIN_RING_SIZE`` accounts AND one endpoint carries
its own evidence (smurf score >= ``ENDPOINT_EVIDENCE_MIN``), AND at least
``MIN_RING_PURITY`` of the ring's members carry evidence of their own. The gates
keep genuine customers out: a large genuine community can look "suspicious" by
size and density alone, and one unusual payment never opens a case on its own.

The scorer never blocks a payment. ``FLAG`` means "route to a human reviewer".
State is a bounded rolling window held as an immutable tuple; every commit
replaces it rather than mutating it. Only trusted ingest should commit
(``commit=True``). The public API scores with ``commit=False`` so a caller
cannot poison the shared history to hide a ring; duplicate ``txn_id`` values
are never added twice, and a reused ``txn_id`` with different content is rejected.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass, replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from models.community_detection.louvain_detector import Community, LouvainClusterDetector
from models.temporal_weighting.smurf_weighting import SMURF_FLOOR, SmurfWeightingEngine, score_transaction_batch

REQUIRED_FIELDS = ("txn_id", "from_account", "to_account", "amount", "timestamp")
DEFAULT_MAX_WINDOW = 5000
DEFAULT_FLAG_THRESHOLD = 0.50
# Louvain dominates scoring time, so the partition is rebuilt every N committed payments.
# A ring formed within the last N payments can therefore be recognised up to N payments late.
DEFAULT_COMMUNITY_REFRESH_EVERY = 10
MIN_RING_SIZE = 3
# Calibrated on seeded synthetic data: 78% of mule accounts vs 1.9% of genuine accounts reach it.
ENDPOINT_EVIDENCE_MIN = 0.30
# Share of ring members that must carry their own evidence ("no innocent bystanders").
MIN_RING_PURITY = 0.30
MERCHANT_TYPE = "MERCHANT"  # account_type whose own activity is not evidence (legitimate hubs)
# A payment is evidence when it, or the combined value of its account pair in the window,
# reaches this amount. One-off small decoys to genuine accounts are ignored (they would
# otherwise dilute a ring, see 05-evaluation.md 7.6c); repeated small payments still count.
MATERIAL_MIN_AMOUNT = SMURF_FLOOR
# Evidence is scored at the default windows and at a slow scale (6x), keeping the stronger
# score per account, so stretching the timeline does not hide a ring.
SLOW_SCALE = SmurfWeightingEngine(velocity_minutes=360, consolidation_hours=36)
# A ring is also judged on payments between its own members, with a third scale that waits up to
# 6 days for the forward (consolidation), so decoys sent to outsiders or a very slow timeline cannot
# dilute the evidence. The velocity window stays at 6 h: a window of 12 h or more made genuine
# communities look like bursts (48 of 97 genuine payments flagged in the small test set).
LONG_FORWARD_SCALE = SmurfWeightingEngine(velocity_minutes=360, consolidation_hours=144)
RING_SCALES = (None, SLOW_SCALE, LONG_FORWARD_SCALE)
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
        amount = float(txn["amount"])
    except (TypeError, ValueError) as exc:
        raise ValueError("payment amount must be numeric") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("payment amount must be a positive finite number")


def _content(txn: Mapping) -> tuple:
    return (txn["from_account"], txn["to_account"], float(txn["amount"]), str(txn["timestamp"]))


def _multi_scale_evidence(window: Sequence[Mapping]) -> Dict:
    fast, slow = score_transaction_batch(list(window)), score_transaction_batch(list(window), SLOW_SCALE)
    return {acc: max(fast[acc], slow[acc], key=lambda s: s.smurf_score) for acc in fast}


def _with_ring_evidence(smurf: Dict, ring: Optional[Community], window: Sequence[Mapping]) -> Dict:
    """Keep the stronger of an account's overall evidence and its evidence from ring-internal payments."""
    if ring is None or ring.size < MIN_RING_SIZE:
        return smurf
    internal = [t for t in window if t["from_account"] in ring.accounts and t["to_account"] in ring.accounts]
    if not internal:
        return smurf
    merged = dict(smurf)
    for engine in RING_SCALES:
        for acc, score in score_transaction_batch(internal, engine).items():
            if acc not in merged or score.smurf_score > merged[acc].smurf_score:
                merged[acc] = score
    return merged


def _pair_is_material(window: Sequence[Mapping], txn: Mapping) -> bool:
    """Same rule as ``_material_window``: the pair's total in the window, not this payment alone."""
    pair = (txn["from_account"], txn["to_account"])
    return (
        sum(float(t["amount"]) for t in window if (t["from_account"], t["to_account"]) == pair) >= MATERIAL_MIN_AMOUNT
    )


def _material_window(window: Sequence[Mapping]) -> List[Mapping]:
    pair_total: Dict[Tuple[str, str], float] = {}
    for t in window:
        key = (t["from_account"], t["to_account"])
        pair_total[key] = pair_total.get(key, 0.0) + float(t["amount"])
    return [t for t in window if pair_total[(t["from_account"], t["to_account"])] >= MATERIAL_MIN_AMOUNT]


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
        community_refresh_every: int = DEFAULT_COMMUNITY_REFRESH_EVERY,
    ):
        if community_refresh_every < 1:
            raise ValueError("community_refresh_every must be at least 1")
        self._accounts: Tuple[Dict, ...] = tuple(dict(a) for a in accounts)
        self._history: Tuple[Dict, ...] = tuple(dict(t) for t in history)[-max_window:]
        self._max_window = max_window
        self._flag_threshold = flag_threshold
        self._refresh_every = community_refresh_every
        self._commits = 0
        self._cached: Optional[Tuple[int, Tuple[Community, ...], frozenset]] = (
            None  # (commits, partition, accounts seen)
        )
        self._lock = threading.Lock()

    @property
    def history_size(self) -> int:
        return len(self._history)

    def score_payment(self, payment: Mapping, commit: bool = True) -> PaymentScore:
        """Score one payment. ``commit`` adds it to the shared window (trusted ingest only)."""
        _validate(payment)
        started = time.perf_counter()
        txn = dict(payment)

        with self._lock:
            accounts = self._accounts
            stored = next((t for t in self._history if t["txn_id"] == txn["txn_id"]), None)
            if stored is not None and _content(stored) != _content(txn):
                raise ValueError("txn_id already used by a different payment")
            window = self._history if stored is not None else (*self._history, txn)[-self._max_window :]
            if commit and stored is None:
                self._history = window
                self._commits += 1
            cached = self._cached
            commits = self._commits

        endpoints = (txn["from_account"], txn["to_account"])
        young = cached is not None and commits - cached[0] < self._refresh_every
        unseen = (
            frozenset(a for a in endpoints if a not in cached[2])
            if young and _pair_is_material(window, txn)
            else frozenset()
        )
        # One first-time account paying into a known ring joins that ring without a full Louvain run;
        # the next scheduled refresh places it properly. Two new accounts could be a ring forming from
        # nothing, so that case still gets a fresh partition.
        newcomer_ok = len(unseen) == 1 and any(a in c.accounts for c in cached[1] for a in endpoints if a not in unseen)
        reuse = young and (not unseen or newcomer_ok)
        communities = cached[1] if reuse else None
        material = _material_window(window)
        return self._score(
            txn,
            material,
            self._with_known_accounts(accounts, material),
            started,
            communities,
            commits,
            commit,
            unseen if newcomer_ok else frozenset(),
        )

    @staticmethod
    def _with_known_accounts(accounts: Tuple[Dict, ...], window: Sequence[Mapping]) -> List[Dict]:
        """Add stub entries for accounts seen only in payments (the graph needs a node)."""
        known = {a["account_id"] for a in accounts}
        seen = {acc for t in window for acc in (t["from_account"], t["to_account"])}
        stubs = [{"account_id": acc} for acc in sorted(seen - known)]
        return [*accounts, *stubs]

    def _score(
        self,
        txn: Dict,
        window: List[Dict],
        accounts: List[Dict],
        started: float,
        communities: Optional[Sequence[Community]],
        commits: int,
        trusted: bool,
        newcomers: frozenset = frozenset(),
    ) -> PaymentScore:
        sender, receiver = txn["from_account"], txn["to_account"]
        smurf = _multi_scale_evidence(window)
        if communities is None:
            communities = tuple(LouvainClusterDetector().detect_clusters(window, accounts))
            if trusted:  # an uncommitted payment must never shape the shared partition
                seen = frozenset(acc for t in window for acc in (t["from_account"], t["to_account"]))
                with self._lock:
                    if self._cached is None or commits >= self._cached[0]:
                        self._cached = (commits, communities, seen)
        ring = self._ring_for(communities, (sender, receiver), newcomers)
        smurf = _with_ring_evidence(smurf, ring, window)

        merchants = frozenset(a["account_id"] for a in accounts if a.get("account_type") == MERCHANT_TYPE)
        endpoint_scores = []
        reasons: List[str] = []
        for acc in (sender, receiver):
            score = None if acc in merchants else smurf.get(acc)
            if score is not None:
                endpoint_scores.append(score.smurf_score)
                reasons.extend(f"{acc}: {code}" for code in score.reason_codes)

        evidence = max(endpoint_scores, default=0.0)
        has_evidence = evidence >= ENDPOINT_EVIDENCE_MIN and self._ring_is_pure(ring, smurf, merchants)
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
    def _ring_is_pure(ring: Optional[Community], smurf: Mapping, merchants: frozenset = frozenset()) -> bool:
        if ring is None or not ring.accounts:
            return False
        with_evidence = sum(
            1
            for a in ring.accounts
            if a not in merchants and a in smurf and smurf[a].smurf_score >= ENDPOINT_EVIDENCE_MIN
        )
        return with_evidence / len(ring.accounts) >= MIN_RING_PURITY

    @staticmethod
    def _ring_for(
        communities: Sequence[Community], endpoints: Sequence[str], newcomers: frozenset = frozenset()
    ) -> Optional[Community]:
        touching = [c for c in communities if any(e in c.accounts for e in endpoints)]
        best = max(touching, key=lambda c: c.suspicion_score, default=None)
        if best is None or not newcomers:
            return best
        return replace(best, accounts=best.accounts | newcomers, size=best.size + len(newcomers))
