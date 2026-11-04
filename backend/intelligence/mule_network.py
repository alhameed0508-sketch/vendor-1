"""The mule-detection core, served to the unified engine through a ring map.

Same rules as the per-payment scorer (``services/realtime_scorer.py`` and ``detection/ring_decision.py``):
multi-scale smurf evidence, Louvain communities, ring-internal evidence, and ``ring_is_flaggable``
(size >= 3, member-evidence purity >= 30 %, strength >= 0.5). The difference is *when* they run: a
refresher rebuilds the map every few seconds or every N committed payments, and each payment only
looks its endpoints up. Measured on this machine, recomputing per payment cost 46-108 ms
(docs/system-design/evidence/capacity_benchmark_result.json).
"""

from __future__ import annotations

import threading
import time
from collections import Counter, deque
from dataclasses import replace
from typing import Callable, Deque, Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple

import networkx as nx
from detection.ring_decision import (
    DEFAULT_FLAG_THRESHOLD,
    ENDPOINT_EVIDENCE_MIN,
    MERCHANT_TYPE,
    MIN_RING_SIZE,
    multi_scale_evidence,
    ring_is_flaggable,
    with_ring_evidence,
)
from intelligence.contracts import DECISIVE, MULE, STRONG, EngineResult, Reason
from services.realtime_scorer import RealtimeScorer, _case_id, _material_window

from models.community_detection.louvain_detector import Community, LouvainClusterDetector

DEFAULT_WINDOW = 5000
DEFAULT_REFRESH_EVERY = 25
DEFAULT_REFRESH_SECONDS = 2.0
OPEN_ALERT_STRENGTH = 0.75
EMPTY_MAP: Dict = {
    "version": 0,
    "built_at": 0.0,
    "payments": 0,
    "evidence": {},
    "rings": {},
    "member_of": {},
    "one_hop": {},
    "victims": {},
}


def ring_core(
    community: Community, window: List[Dict], accounts: List[Dict], detector: LouvainClusterDetector, evidence: Mapping
) -> Tuple[Optional[Community], frozenset]:
    """Separate a ring's members from the people who only paid into it (the "bystander dilution" fix).

    Inside the community, an account that sends money in, receives nothing from the community and
    shows no mule pattern of its own is a payer (usually a victim), not a ring member. Real mules
    collect from many one-off payers, so counting those payers hides the ring in the purity test; and
    calling a defrauded customer a ring member would be a false positive of the worst kind. Accounts
    that were attached to the community only through those payers (the victim's usual shop, a friend)
    are then left with no link to the core and are dropped too. The core is re-scored with the same
    Louvain scoring rules over the members alone.
    Returns (core community or None, every excluded account).
    """
    members = community.accounts
    sent, received = Counter(), Counter()
    internal = [t for t in window if t["from_account"] in members and t["to_account"] in members]
    for t in internal:
        sent[t["from_account"]] += 1
        received[t["to_account"]] += 1
    leaves = frozenset(
        a
        for a in members
        if received[a] == 0 and sent[a] > 0 and (a not in evidence or evidence[a].smurf_score < ENDPOINT_EVIDENCE_MIN)
    )
    if not leaves:
        return community, frozenset()
    # Same graph Louvain partitioned (payment edges plus shared-device edges), restricted to the core.
    graph = getattr(detector, "_graph", None)
    if graph is None:
        graph = nx.Graph()
        graph.add_edges_from((t["from_account"], t["to_account"]) for t in internal)
    core = set(members) - leaves
    while True:  # drop accounts left with no link to another core member, until nothing changes
        linked = {a for a in core if graph.has_node(a) and any(b in core and b != a for b in graph.neighbors(a))}
        if linked == core:
            break
        core = linked
    excluded = frozenset(members - core)
    if len(core) < MIN_RING_SIZE:
        return None, excluded
    leaves = excluded
    sub = graph.subgraph(core)
    n = len(core)
    edges = sub.number_of_edges()
    density = edges / (n * (n - 1) / 2) if n > 1 else 0.0
    devices: Dict[str, set] = {}
    ips: Dict[str, set] = {}
    for t in window:
        src = t["from_account"]
        if src in core:
            if t.get("device_id"):
                devices.setdefault(t["device_id"], set()).add(src)
            if t.get("ip_address"):
                ips.setdefault(t["ip_address"], set()).add(src)
    scored = replace(
        community,
        accounts=core,
        size=n,
        density=density,
        internal_edges=edges,
        shared_devices=[d for d, accs in devices.items() if len(accs) >= 2],
        shared_ips=[i for i, accs in ips.items() if len(accs) >= 2],
    )
    scored.suspicion_score = detector._score_community(scored, accounts, core)
    scored.reason_codes = detector._reason_codes(scored)
    scored.is_mule_cluster = scored.suspicion_score >= detector.SUSPICION_THRESHOLD
    return scored, leaves


class MuleNetworkIntel:
    """Maintains the committed payment window and an immutable, periodically rebuilt ring map."""

    def __init__(
        self,
        accounts: Iterable[Mapping] = (),
        window: int = DEFAULT_WINDOW,
        refresh_every: int = DEFAULT_REFRESH_EVERY,
        refresh_seconds: float = DEFAULT_REFRESH_SECONDS,
        flag_threshold: float = DEFAULT_FLAG_THRESHOLD,
        background: bool = False,
        alert_members: Optional[Callable[[], FrozenSet[str]]] = None,
    ):
        self._accounts: Dict[str, Dict] = {a["account_id"]: dict(a) for a in accounts}
        self._window: Deque[Dict] = deque(maxlen=window)
        self._seen_txn: Dict[str, None] = {}
        self._refresh_every = refresh_every
        self._refresh_seconds = refresh_seconds
        self._threshold = flag_threshold
        self._background = background
        self._alert_members_fn = alert_members
        self._alert_members: FrozenSet[str] = frozenset()
        self._map: Dict = EMPTY_MAP
        self._since_refresh = 0
        self._last_refresh = 0.0
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ writes
    def add(self, payment: Mapping, allow_refresh: bool = True) -> None:
        """Commit one trusted payment to the window; schedule a rebuild when one is due.

        ``allow_refresh=False`` defers the rebuild (bulk warm-up); call ``refresh()`` afterwards.
        """
        txn_id = str(payment["txn_id"])
        with self._lock:
            if txn_id in self._seen_txn:
                return
            self._seen_txn[txn_id] = None
            if len(self._seen_txn) > 4 * self._window.maxlen:
                for old in list(self._seen_txn)[: self._window.maxlen]:
                    del self._seen_txn[old]
            self._window.append(dict(payment))
            self._since_refresh += 1
            due = allow_refresh and (
                self._since_refresh >= self._refresh_every
                or (time.monotonic() - self._last_refresh >= self._refresh_seconds and self._since_refresh > 0)
            )
        if due:
            self._schedule()

    def add_accounts(self, accounts: Iterable[Mapping]) -> None:
        with self._lock:
            for a in accounts:
                self._accounts[a["account_id"]] = dict(a)

    def refresh(self) -> Dict:
        """Rebuild the ring map from the current window (synchronously). Returns the new map."""
        with self._lock:
            window = list(self._window)
            accounts = tuple(self._accounts.values())
            self._since_refresh = 0
            self._last_refresh = time.monotonic()
            version = self._map["version"] + 1
        if self._alert_members_fn is not None:
            try:
                self._alert_members = frozenset(self._alert_members_fn())
            except Exception:  # noqa: BLE001 - alerts are an extra signal; keep the last good set
                pass
        new_map = self._build(window, accounts, version)
        with self._lock:
            if new_map["version"] > self._map["version"]:
                self._map = new_map
        return new_map

    def _schedule(self) -> None:
        if not self._background:
            self.refresh()
            return
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self.refresh, daemon=True, name="ring-map-refresh")
            self._worker.start()

    def wait(self, timeout: Optional[float] = None) -> None:
        worker = self._worker
        if worker is not None:
            worker.join(timeout)

    def _build(self, window: List[Dict], accounts, version: int) -> Dict:
        material = _material_window(window)
        merchants = frozenset(a["account_id"] for a in accounts if a.get("account_type") == MERCHANT_TYPE)
        if not material:
            return {**EMPTY_MAP, "version": version, "built_at": time.time(), "payments": len(window)}
        known = RealtimeScorer._with_known_accounts(accounts, material)
        evidence = multi_scale_evidence(material)
        detector = LouvainClusterDetector()
        communities = detector.detect_clusters(material, known)
        rings, member_of, victims = {}, {}, {}
        for found in communities:
            if found.size < MIN_RING_SIZE:
                continue
            community, leaves = ring_core(found, material, known, detector, evidence)
            if community is None:
                continue
            ring_evidence = with_ring_evidence(evidence, community, material)
            if not ring_is_flaggable(community, ring_evidence, merchants, self._threshold):
                continue
            members = sorted(community.accounts)
            best = max(
                (ring_evidence[a].smurf_score for a in members if a in ring_evidence and a not in merchants),
                default=0.0,
            )
            ring_id = _case_id(members)
            rings[ring_id] = {
                "ring_id": ring_id,
                "members": members,
                "size": len(members),
                "strength": round(min(1.0, max(community.suspicion_score, best)), 4),
                "reason_codes": list(community.reason_codes)[:4],
                "victims_excluded": len(leaves),
            }
            for acc in leaves:
                victims[acc] = ring_id
            for acc in members:
                member_of[acc] = ring_id
                if acc in ring_evidence:
                    evidence[acc] = max(
                        evidence.get(acc, ring_evidence[acc]), ring_evidence[acc], key=lambda s: s.smurf_score
                    )
        one_hop = {}
        for t in material:
            a, b = t["from_account"], t["to_account"]
            if a in member_of and b not in member_of:
                one_hop.setdefault(b, member_of[a])
            if b in member_of and a not in member_of:
                one_hop.setdefault(a, member_of[b])
        compact = {
            acc: (round(s.smurf_score, 4), tuple(s.reason_codes[:3]))
            for acc, s in evidence.items()
            if acc not in merchants and s.smurf_score > 0
        }
        return {
            "version": version,
            "built_at": time.time(),
            "payments": len(window),
            "evidence": compact,
            "rings": rings,
            "member_of": member_of,
            "one_hop": one_hop,
            "merchants": merchants,
            "victims": victims,
        }

    # ------------------------------------------------------------------- reads
    @property
    def ring_map(self) -> Dict:
        return self._map

    def status(self) -> Dict:
        m = self._map
        return {
            "version": m["version"],
            "age_seconds": round(time.time() - m["built_at"], 1) if m["built_at"] else None,
            "payments_in_window": len(self._window),
            "rings": len(m["rings"]),
            "accounts_with_evidence": len(m["evidence"]),
        }

    def one_hop_ring(self, account: str) -> Optional[Dict]:
        ring_id = self._map["one_hop"].get(account)
        return self._map["rings"].get(ring_id) if ring_id else None

    def assess(self, payer: str, payee: str) -> EngineResult:
        m = self._map
        reasons: List[Reason] = []
        for role, acc in (("payer", payer), ("payee", payee)):
            ev = m["evidence"].get(acc)
            if ev and ev[0] >= ENDPOINT_EVIDENCE_MIN:
                codes = ", ".join(ev[1]) or "smurf pattern"
                reasons.append(
                    Reason("MN01", f"The {role} {acc} shows its own mule pattern ({codes}).", min(0.9, ev[0]), STRONG)
                )
            ring_id = m["member_of"].get(acc)
            if ring_id:
                ring = m["rings"][ring_id]
                reasons.append(
                    Reason(
                        "MN02",
                        f"The {role} {acc} is in mule ring {ring_id} ({ring['size']} accounts) "
                        "found by network detection.",
                        max(0.85, ring["strength"]),
                        DECISIVE,
                    )
                )
        if payee in self._alert_members and not m["member_of"].get(payee):
            reasons.append(
                Reason(
                    "MN03",
                    f"The payee {payee} is part of an open mule alert in the investigation queue.",
                    OPEN_ALERT_STRENGTH,
                    STRONG,
                )
            )
        features = {
            "payer_evidence": m["evidence"].get(payer, (0.0, ()))[0],
            "payee_evidence": m["evidence"].get(payee, (0.0, ()))[0],
            "in_ring": float(bool(m["member_of"].get(payer) or m["member_of"].get(payee))),
        }
        return EngineResult(
            MULE,
            tuple(reasons),
            data_available=True,
            features=features,
            note=f"ring map v{m['version']} over {m['payments']} payments",
        )
