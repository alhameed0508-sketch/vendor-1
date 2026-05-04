"""
MuleCatch Detection Pipeline
=============================
Orchestrates the four-layer detection stack:
  Layer 1: Rule engine (known patterns, fast)
  Layer 2: Smurf-weighting algorithm (temporal analysis)
  Layer 3: Louvain community detection (network topology)
  Layer 4: GNN scoring (graph learning, optional)

Produces consolidated Alert objects with subgraph data.
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.temporal_weighting.smurf_weighting import score_transaction_batch, AccountScore
from models.community_detection.louvain_detector import LouvainClusterDetector, Community
from models.behavioral.baseline import compute_baselines, BaselineDeviation
from explainability.explainer import explain_alert
from explainability.narrative_generator import generate_narrative
from detection.mule_classifier import classify_cluster


# ── Data models ───────────────────────────────────────────────────────────

@dataclass
class AlertNode:
    account_id: str
    role: str           # SOURCE | MULE | AGGREGATOR | UNKNOWN
    smurf_score: float
    bank: str
    city: str
    account_age_days: int
    kyc_status: str
    upi_id: str
    betweenness: float = 0.0    # betweenness centrality (0-1, higher = more bridging)
    pagerank: float = 0.0       # PageRank score (higher = more influential)
    baseline_deviation: float = 0.0  # behavioral deviation from historical baseline


@dataclass
class AlertEdge:
    from_account: str
    to_account: str
    total_amount: float
    txn_count: int
    pattern: str
    timestamps: List[str]


@dataclass
class Alert:
    alert_id: str
    cluster_id: Optional[str]
    severity: str           # CRITICAL | HIGH | MEDIUM
    confidence: float
    risk_score: float
    total_amount: float
    txn_count: int
    account_count: int
    nodes: List[AlertNode]
    edges: List[AlertEdge]
    reason_codes: List[str]
    shared_devices: List[str]
    shared_ips: List[str]
    created_at: str
    status: str = "OPEN"    # OPEN | UNDER_REVIEW | RESOLVED | FALSE_POSITIVE
    investigator_notes: str = ""
    gnn_score: Optional[float] = None
    explanation: Optional[Dict] = None
    narrative: Optional[Dict] = None
    mule_classification: Optional[Dict] = None


# ── Rule engine ───────────────────────────────────────────────────────────

class RuleEngine:
    """
    Fast, deterministic rules applied before ML scoring.
    19 behavioral patterns aligned with RBI/RBIH MuleHunter framework.
    """

    RULES = [
        # ── Original 4 rules ────────────────────────────────────────────
        ("R01", "Account age < 7 days",
         lambda a, txns: a.get("account_age_days", 999) < 7),
        ("R02", "> 20 transactions in 24h",
         lambda a, txns: _count_outgoing(a, txns) > 20),
        ("R03", "KYC pending with high volume",
         lambda a, txns: a.get("kyc_status") == "PENDING" and _count_outgoing(a, txns) > 5),
        ("R04", "Amounts structured below ₹50k threshold",
         lambda a, txns: _all_near_ceiling(a["account_id"], txns)),

        # ── MuleHunter-aligned behavioral patterns ──────────────────────
        ("R05", "Dormant account suddenly activated",
         lambda a, txns: a.get("account_age_days", 0) > 180 and
                         a.get("avg_monthly_txn", 0) < 3 and _count_outgoing(a, txns) > 8),
        ("R06", "Same-day credit-debit (pass-through)",
         lambda a, txns: _same_day_credit_debit(a["account_id"], txns)),
        ("R07", "Funds received from multiple sources then consolidated",
         lambda a, txns: _fan_in_then_out(a["account_id"], txns)),
        ("R08", "Night-time high-value transactions (11PM-5AM)",
         lambda a, txns: _night_transactions(a["account_id"], txns)),
        ("R09", "Round-trip transfer detected",
         lambda a, txns: _round_trip(a["account_id"], txns)),
        ("R10", "Sudden beneficiary addition spike",
         lambda a, txns: _sudden_beneficiary_spike(a["account_id"], txns)),
        ("R11", "Cross-bank rapid layering",
         lambda a, txns: _cross_bank_layering(a, txns)),
        ("R12", "Identical amounts to multiple recipients",
         lambda a, txns: _identical_amounts(a["account_id"], txns)),
        ("R13", "Geographic anomaly — multi-city in 24h",
         lambda a, txns: _geographic_anomaly(a["account_id"], txns)),
        ("R14", "Split transaction pattern (< ₹10k each, > ₹1L total)",
         lambda a, txns: _split_transactions(a["account_id"], txns)),
        ("R15", "High-risk UPI handle pattern",
         lambda a, txns: _high_risk_upi(a)),
        ("R16", "Account used as intermediary only (no self-use)",
         lambda a, txns: _intermediary_only(a["account_id"], txns)),
        ("R17", "Velocity acceleration — txn rate doubling",
         lambda a, txns: _velocity_acceleration(a["account_id"], txns)),
        ("R18", "Shared device across multiple accounts",
         lambda a, txns: _shared_device(a["account_id"], txns)),
        ("R19", "Rapid fund sweep — balance cleared within hours",
         lambda a, txns: _rapid_fund_sweep(a["account_id"], txns)),

        # ── 72-hour early detection (BioCatch research) ──────────────
        ("R20", "72-hour behavioral anomaly — high activity within 3 days of opening",
         lambda a, txns: _seventy_two_hour_anomaly(a, txns)),
    ]

    def evaluate(
        self, accounts: List[Dict], transactions: List[Dict]
    ) -> Dict[str, List[str]]:
        results: Dict[str, List[str]] = {}
        for acc in accounts:
            hits = [
                f"{code}: {desc}"
                for code, desc, fn in self.RULES
                if fn(acc, transactions)
            ]
            if hits:
                results[acc["account_id"]] = hits
        return results


# ── Rule helper functions ─────────────────────────────────────────────────

def _count_outgoing(a: Dict, txns: List[Dict]) -> int:
    return sum(1 for t in txns if t["from_account"] == a["account_id"])


def _all_near_ceiling(account_id: str, transactions: List[Dict]) -> bool:
    amounts = [t["amount"] for t in transactions
               if t["from_account"] == account_id
               and 40000 <= float(t["amount"]) < 50000]
    total = sum(1 for t in transactions if t["from_account"] == account_id)
    return total > 3 and len(amounts) / max(total, 1) > 0.7


def _same_day_credit_debit(account_id: str, txns: List[Dict]) -> bool:
    """Detects accounts that receive and re-send within the same day."""
    incoming_days = set()
    outgoing_days = set()
    for t in txns:
        day = t["timestamp"][:10] if isinstance(t["timestamp"], str) else str(t["timestamp"])[:10]
        if t["to_account"] == account_id:
            incoming_days.add(day)
        if t["from_account"] == account_id:
            outgoing_days.add(day)
    overlap = incoming_days & outgoing_days
    return len(overlap) >= 2


def _fan_in_then_out(account_id: str, txns: List[Dict]) -> bool:
    """Detects consolidation: many sources → one account → one destination."""
    senders = set(t["from_account"] for t in txns if t["to_account"] == account_id)
    recipients = set(t["to_account"] for t in txns if t["from_account"] == account_id)
    return len(senders) >= 3 and len(recipients) >= 1


def _night_transactions(account_id: str, txns: List[Dict]) -> bool:
    """High-value transactions between 11PM-5AM."""
    night_count = 0
    for t in txns:
        if t["from_account"] != account_id:
            continue
        ts = t["timestamp"]
        hour = int(ts[11:13]) if isinstance(ts, str) and len(ts) > 13 else 12
        if hour >= 23 or hour < 5:
            if float(t["amount"]) > 10000:
                night_count += 1
    return night_count >= 3


def _round_trip(account_id: str, txns: List[Dict]) -> bool:
    """Detects A→B and B→A transfers."""
    sent_to = set(t["to_account"] for t in txns if t["from_account"] == account_id)
    received_from = set(t["from_account"] for t in txns if t["to_account"] == account_id)
    return len(sent_to & received_from) >= 1


def _sudden_beneficiary_spike(account_id: str, txns: List[Dict]) -> bool:
    """Suddenly transacting with 5+ new recipients."""
    recipients = set(t["to_account"] for t in txns if t["from_account"] == account_id)
    return len(recipients) >= 5


def _cross_bank_layering(a: Dict, txns: List[Dict]) -> bool:
    """Transfers to recipients across 3+ different banks."""
    recipient_banks = set()
    for t in txns:
        if t["from_account"] == a["account_id"]:
            # In real systems, recipient bank is in txn data;
            # here we check if this account transacts with diverse nodes
            recipient_banks.add(t["to_account"][:4])  # bank prefix proxy
    return len(recipient_banks) >= 3


def _identical_amounts(account_id: str, txns: List[Dict]) -> bool:
    """Same exact amount sent to multiple different recipients."""
    from collections import Counter
    amounts_by_recipient = {}
    for t in txns:
        if t["from_account"] != account_id:
            continue
        amt = round(float(t["amount"]), 2)
        amounts_by_recipient.setdefault(amt, set()).add(t["to_account"])
    return any(len(recipients) >= 3 for recipients in amounts_by_recipient.values())


def _geographic_anomaly(account_id: str, txns: List[Dict]) -> bool:
    """Transactions from multiple cities in a short window."""
    cities = set()
    for t in txns:
        if t["from_account"] == account_id and t.get("city"):
            cities.add(t["city"])
    return len(cities) >= 3


def _split_transactions(account_id: str, txns: List[Dict]) -> bool:
    """Many small transactions that aggregate to a large total."""
    outgoing = [float(t["amount"]) for t in txns if t["from_account"] == account_id]
    small = [a for a in outgoing if a < 10000]
    return len(small) >= 5 and sum(small) >= 100000


def _high_risk_upi(a: Dict) -> bool:
    """UPI handle associated with known fraud patterns."""
    upi = a.get("upi_id", "")
    # Random/disposable UPI handles with numeric-heavy patterns
    if not upi:
        return False
    digit_ratio = sum(1 for c in upi if c.isdigit()) / max(len(upi), 1)
    return digit_ratio > 0.6 and len(upi) > 10


def _intermediary_only(account_id: str, txns: List[Dict]) -> bool:
    """Account only receives and re-sends, never self-use."""
    incoming = sum(1 for t in txns if t["to_account"] == account_id)
    outgoing = sum(1 for t in txns if t["from_account"] == account_id)
    return incoming >= 3 and outgoing >= 3


def _velocity_acceleration(account_id: str, txns: List[Dict]) -> bool:
    """Transaction rate more than doubles compared to historical average."""
    avg_monthly = 10  # default
    current_count = sum(1 for t in txns if t["from_account"] == account_id)
    return current_count > avg_monthly * 2


def _shared_device(account_id: str, txns: List[Dict]) -> bool:
    """Multiple accounts using the same device_id."""
    my_devices = set(
        t.get("device_id", "") for t in txns
        if t["from_account"] == account_id and t.get("device_id")
    )
    if not my_devices:
        return False
    for dev in my_devices:
        other_accounts = set(
            t["from_account"] for t in txns
            if t.get("device_id") == dev and t["from_account"] != account_id
        )
        if other_accounts:
            return True
    return False


def _rapid_fund_sweep(account_id: str, txns: List[Dict]) -> bool:
    """Incoming funds swept out within same window (balance near zero)."""
    incoming_total = sum(float(t["amount"]) for t in txns if t["to_account"] == account_id)
    outgoing_total = sum(float(t["amount"]) for t in txns if t["from_account"] == account_id)
    if incoming_total < 10000:
        return False
    # If >90% of incoming is swept out, flag it
    return outgoing_total / max(incoming_total, 1) > 0.90


def _seventy_two_hour_anomaly(a: Dict, txns: List[Dict]) -> bool:
    """
    BioCatch-inspired: 48% of mule accounts show behavioral inconsistencies
    within 72 hours of account opening. Flag accounts <3 days old with
    abnormally high outgoing activity.
    """
    age_days = a.get("account_age_days", 999)
    if age_days > 3:
        return False
    outgoing = sum(1 for t in txns if t["from_account"] == a["account_id"])
    outgoing_amount = sum(
        float(t["amount"]) for t in txns if t["from_account"] == a["account_id"]
    )
    # Account <72h old with 5+ outgoing txns or >₹1L outgoing volume
    return outgoing >= 5 or outgoing_amount >= 100000


# ── GNN scorer (lazy import, optional) ───────────────────────────────────

def _try_load_gnn_scorer():
    """Attempt to load the GNN scorer; returns None if unavailable."""
    try:
        from models.gnn.gnn_model import GNNScorer
        scorer = GNNScorer()
        return scorer
    except Exception:
        return None


# ── Detection pipeline ────────────────────────────────────────────────────

class DetectionPipeline:
    """
    End-to-end pipeline.  Target latency: < 60 seconds for 10k transactions.
    """

    # Default scoring weights
    DEFAULT_LOUVAIN_WEIGHT = 0.50
    DEFAULT_SMURF_WEIGHT = 0.30
    DEFAULT_GNN_WEIGHT = 0.20

    # Fallback weights when GNN is unavailable
    FALLBACK_LOUVAIN_WEIGHT = 0.60
    FALLBACK_SMURF_WEIGHT = 0.40

    def __init__(
        self,
        smurf_threshold: Optional[float] = None,
        suspicion_threshold: Optional[float] = None,
    ):
        self.rule_engine = RuleEngine()
        self.cluster_detector = LouvainClusterDetector()
        self._gnn_scorer = _try_load_gnn_scorer()
        self._gnn_available = self._gnn_scorer is not None

        # Threshold overrides from feedback engine
        self._smurf_threshold = smurf_threshold
        self._suspicion_threshold = suspicion_threshold

    def run(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> List[Alert]:
        start = datetime.now()

        # Layer 1: rules
        rule_hits = self.rule_engine.evaluate(accounts, transactions)

        # Layer 2: smurf-weighting
        smurf_scores: Dict[str, AccountScore] = score_transaction_batch(transactions)

        # Layer 2b: behavioral baseline comparison
        baselines = compute_baselines(accounts, transactions)

        # Layer 3: community detection
        communities = self.cluster_detector.detect_clusters(transactions, accounts)

        # Layer 3b: centrality scoring (betweenness + PageRank)
        centrality = self.cluster_detector.compute_centrality()

        # Layer 4: GNN scoring (optional)
        gnn_predictions = {}
        if self._gnn_available and self._gnn_scorer is not None:
            try:
                preds = self._gnn_scorer.predict(accounts, transactions, smurf_scores)
                gnn_predictions = {p.account_id: p for p in preds}
            except Exception as exc:
                print(f"GNN scoring failed (falling back): {exc}")

        # Build alerts from flagged communities
        alerts = []
        acc_map = {a["account_id"]: a for a in accounts}
        flagged_communities = [c for c in communities if c.is_mule_cluster]

        for community in flagged_communities:
            alert = self._build_alert(
                community,
                transactions,
                acc_map,
                smurf_scores,
                rule_hits,
                gnn_predictions,
                centrality,
                baselines,
            )
            alerts.append(alert)

        # Layer 5: Explainability — generate explanations for each alert
        for alert in alerts:
            try:
                alert_dict = {
                    "alert_id": alert.alert_id,
                    "risk_score": alert.risk_score,
                    "severity": alert.severity,
                    "account_count": alert.account_count,
                    "nodes": [vars(n) for n in alert.nodes],
                    "edges": [vars(e) for e in alert.edges],
                    "reason_codes": alert.reason_codes,
                    "shared_devices": alert.shared_devices,
                    "shared_ips": alert.shared_ips,
                    "gnn_score": alert.gnn_score,
                }
                explanation = explain_alert(alert_dict, smurf_scores)
                alert.explanation = explanation.to_dict()
            except Exception as exc:
                print(f"Explainability failed for {alert.alert_id}: {exc}")

        # Layer 6: Mule type classification + narrative generation
        for alert in alerts:
            try:
                alert_dict = {
                    "alert_id": alert.alert_id,
                    "risk_score": alert.risk_score,
                    "severity": alert.severity,
                    "total_amount": alert.total_amount,
                    "txn_count": alert.txn_count,
                    "account_count": alert.account_count,
                    "nodes": [vars(n) for n in alert.nodes],
                    "edges": [vars(e) for e in alert.edges],
                    "reason_codes": alert.reason_codes,
                    "shared_devices": alert.shared_devices,
                    "shared_ips": alert.shared_ips,
                    "gnn_score": alert.gnn_score,
                    "explanation": alert.explanation or {},
                }
                classification = classify_cluster(alert_dict, transactions)
                alert.mule_classification = classification

                narrative = generate_narrative(alert_dict, classification)
                alert.narrative = narrative.to_dict()
            except Exception as exc:
                print(f"Classification/narrative failed for {alert.alert_id}: {exc}")

        elapsed = (datetime.now() - start).total_seconds()
        gnn_status = "with GNN" if gnn_predictions else "without GNN"
        print(f"Detection pipeline ({gnn_status}): {len(transactions)} txns -> "
              f"{len(flagged_communities)} alerts in {elapsed:.2f}s")

        return sorted(alerts, key=lambda a: -a.risk_score)

    def _build_alert(
        self,
        community: Community,
        transactions: List[Dict],
        acc_map: Dict[str, Dict],
        smurf_scores: Dict[str, AccountScore],
        rule_hits: Dict[str, List[str]],
        gnn_predictions: Dict,
        centrality: Dict[str, Dict[str, float]] = None,
        baselines: Dict[str, BaselineDeviation] = None,
    ) -> Alert:
        members = community.accounts

        # Filter transactions within this community
        community_txns = [
            t for t in transactions
            if t["from_account"] in members or t["to_account"] in members
        ]

        # Build nodes
        centrality = centrality or {}
        baselines = baselines or {}
        nodes = []
        for acc_id in members:
            acc = acc_map.get(acc_id, {})
            ss  = smurf_scores.get(acc_id)
            cs  = centrality.get(acc_id, {})
            bl  = baselines.get(acc_id)
            nodes.append(AlertNode(
                account_id=acc_id,
                role=acc.get("role", "UNKNOWN"),
                smurf_score=ss.smurf_score if ss else 0.0,
                bank=acc.get("bank", ""),
                city=acc.get("city", ""),
                account_age_days=acc.get("account_age_days", 0),
                kyc_status=acc.get("kyc_status", "UNKNOWN"),
                upi_id=acc.get("upi_id", ""),
                betweenness=cs.get("betweenness", 0.0),
                pagerank=cs.get("pagerank", 0.0),
                baseline_deviation=bl.composite_score if bl else 0.0,
            ))

        # Build edges (aggregate multiple txns between same pair)
        edge_map: Dict[tuple, AlertEdge] = {}
        for t in community_txns:
            key = (t["from_account"], t["to_account"])
            if key not in edge_map:
                edge_map[key] = AlertEdge(
                    from_account=t["from_account"],
                    to_account=t["to_account"],
                    total_amount=0,
                    txn_count=0,
                    pattern=t.get("pattern", "NORMAL"),
                    timestamps=[],
                )
            edge_map[key].total_amount += float(t["amount"])
            edge_map[key].txn_count += 1
            edge_map[key].timestamps.append(t["timestamp"])

        # Compile reason codes
        all_codes = list(community.reason_codes)
        for acc_id in members:
            ss = smurf_scores.get(acc_id)
            if ss:
                all_codes.extend(ss.reason_codes)
            all_codes.extend(rule_hits.get(acc_id, []))
            bl = baselines.get(acc_id)
            if bl:
                all_codes.extend(bl.reason_codes)
        unique_codes = list(dict.fromkeys(all_codes))[:10]   # deduplicate, max 10

        # Composite risk score with optional GNN layer
        # Use blend of max + avg smurf scores: cluster risk is driven by
        # the highest-scoring member (SOURCE), not diluted by low-scoring mules
        member_smurf = [smurf_scores[a].smurf_score for a in members if a in smurf_scores]
        if member_smurf:
            max_smurf = max(member_smurf)
            mean_smurf = sum(member_smurf) / len(member_smurf)
            avg_smurf = 0.6 * max_smurf + 0.4 * mean_smurf
        else:
            avg_smurf = 0.0

        avg_gnn = None
        if gnn_predictions:
            gnn_scores = [
                gnn_predictions[a].mule_probability
                for a in members if a in gnn_predictions
            ]
            if gnn_scores:
                max_gnn = max(gnn_scores)
                mean_gnn = sum(gnn_scores) / len(gnn_scores)
                avg_gnn = 0.6 * max_gnn + 0.4 * mean_gnn

        # Centrality amplifier: accounts with high betweenness are network
        # bridges (money laundering bottlenecks); high PageRank means they
        # receive flow from many paths.  max() captures the most critical node.
        member_betweenness = [centrality.get(a, {}).get("betweenness", 0) for a in members]
        member_pagerank    = [centrality.get(a, {}).get("pagerank", 0)    for a in members]
        max_betweenness = max(member_betweenness) if member_betweenness else 0
        max_pagerank    = max(member_pagerank)    if member_pagerank    else 0
        # Centrality boost: up to +0.08 from betweenness, +0.04 from PageRank
        centrality_boost = min(max_betweenness * 0.4, 0.08) + min(max_pagerank * 4, 0.04)

        # Behavioral baseline boost: up to +0.06 from deviation
        member_baselines = [baselines.get(a, BaselineDeviation(a)).composite_score for a in members]
        max_baseline_dev = max(member_baselines) if member_baselines else 0
        baseline_boost = min(max_baseline_dev * 0.1, 0.06)

        if avg_gnn is not None:
            # 4-layer scoring: 50% Louvain + 30% Smurf + 20% GNN + boosts
            risk_score = (
                self.DEFAULT_LOUVAIN_WEIGHT * community.suspicion_score +
                self.DEFAULT_SMURF_WEIGHT * avg_smurf +
                self.DEFAULT_GNN_WEIGHT * avg_gnn +
                centrality_boost +
                baseline_boost
            )
        else:
            # 3-layer fallback: 60% Louvain + 40% Smurf + boosts
            risk_score = (
                self.FALLBACK_LOUVAIN_WEIGHT * community.suspicion_score +
                self.FALLBACK_SMURF_WEIGHT * avg_smurf +
                centrality_boost +
                baseline_boost
            )

        # Structural risk amplifiers
        # Large clusters with many reason codes are more suspicious
        if len(members) >= 12 and len(unique_codes) >= 6:
            risk_score += 0.10
        elif len(members) >= 10 and len(unique_codes) >= 5:
            risk_score += 0.05

        # Multiple shared fingerprints amplify risk
        if len(community.shared_devices) >= 3:
            risk_score += 0.08
        elif len(community.shared_devices) >= 2:
            risk_score += 0.04

        risk_score = min(risk_score, 0.99)

        confidence = min(risk_score + 0.05 * len(unique_codes), 1.0)

        total_amount = sum(float(t["amount"]) for t in community_txns)

        severity = (
            "CRITICAL" if risk_score >= 0.80 else
            "HIGH"     if risk_score >= 0.60 else
            "MEDIUM"
        )

        # Try to get cluster_id from any member
        cluster_id = None
        for acc_id in members:
            acc = acc_map.get(acc_id, {})
            if acc.get("cluster_id"):
                cluster_id = acc["cluster_id"]
                break

        return Alert(
            alert_id=f"ALT_{uuid.uuid4().hex[:10].upper()}",
            cluster_id=cluster_id,
            severity=severity,
            confidence=round(confidence, 3),
            risk_score=round(risk_score, 3),
            total_amount=round(total_amount, 2),
            txn_count=len(community_txns),
            account_count=len(members),
            nodes=nodes,
            edges=list(edge_map.values()),
            reason_codes=unique_codes,
            shared_devices=community.shared_devices,
            shared_ips=community.shared_ips,
            created_at=datetime.utcnow().isoformat(),
            gnn_score=round(avg_gnn, 3) if avg_gnn is not None else None,
        )


if __name__ == "__main__":
    sys.path.insert(0, ".")
    from data.synthetic.generator import build_full_dataset

    print("Running detection pipeline self-test...")
    dataset = build_full_dataset(num_clusters=3, num_legit_accounts=30)
    pipeline = DetectionPipeline()
    alerts = pipeline.run(dataset["transactions"], dataset["accounts"])

    print(f"\n{len(alerts)} alerts generated:")
    for a in alerts:
        gnn_str = f"  gnn={a.gnn_score:.3f}" if a.gnn_score is not None else ""
        print(f"  [{a.severity}] {a.alert_id}  score={a.risk_score:.3f}{gnn_str}  "
              f"accounts={a.account_count}  amount=₹{a.total_amount:,.0f}")
        for rc in a.reason_codes[:3]:
            print(f"    {rc}")
