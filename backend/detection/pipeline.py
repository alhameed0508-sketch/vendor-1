"""
MuleCatch Detection Pipeline
=============================
Orchestrates the multi-layer detection stack:
  Layer 1: Rule engine (known patterns, fast)
  Layer 2: Smurf-weighting algorithm (temporal analysis)
  Layer 2b: Behavioral baseline comparison
  Layer 2c: Transaction semantics analysis
  Layer 2d: Device profiling
  Layer 2e: Markov state transition scoring (temporal lifecycle)
  Layer 2f: PyOD label-free anomaly scoring (cold start)
  Layer 3: Louvain community detection (network topology)
  Layer 4: GNN scoring (graph learning, optional)
  Layer 5: GenAI triage (LLM reviews uncertain alerts)
  Layer 6: Explainability (SHAP + rule-based explanations)
  Layer 7: Mule type classification + narrative generation

Produces consolidated Alert objects with subgraph data.
"""

# ruff: noqa: E402

from __future__ import annotations

import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Module-level constants (rule thresholds) ──────────────────────────────
# These thresholds are used by the rule-engine helper functions.

# R04: Structured transactions — amounts between these bounds trigger the rule
STRUCTURED_AMOUNT_LOWER = 40000  # lower bound of "near ₹50k ceiling" band
STRUCTURED_AMOUNT_UPPER = 50000  # upper bound (the ₹50k reporting threshold)
STRUCTURED_MIN_TXNS = 3  # minimum outgoing txns to evaluate
STRUCTURED_RATIO_THRESHOLD = 0.7  # fraction of txns near ceiling to flag

# R14: Split transactions
SPLIT_TXN_AMOUNT_UPPER = 10000  # individual txn ceiling (< ₹10k each)
SPLIT_TXN_MIN_COUNT = 5  # minimum number of small txns
SPLIT_TXN_TOTAL_THRESHOLD = 100000  # aggregate total must exceed ₹1L

# R15: High-risk UPI handles
UPI_DIGIT_RATIO_THRESHOLD = 0.6  # fraction of digits in UPI handle
UPI_MIN_LENGTH = 10  # minimum UPI handle length

# R20: 72-hour anomaly
EARLY_ANOMALY_AGE_DAYS = 3  # account age threshold (days)
EARLY_ANOMALY_MIN_TXNS = 5  # minimum outgoing txns
EARLY_ANOMALY_MIN_AMOUNT = 100000  # minimum outgoing volume (₹1L)

from detection.mule_classifier import classify_cluster  # noqa: E402
from explainability.explainer import explain_alert  # noqa: E402
from explainability.narrative_generator import generate_narrative  # noqa: E402

from models.anomaly.unsupervised_scorer import (  # noqa: E402
    AnomalyPrediction,
    UnsupervisedAccountScorer,
)
from models.behavioral.baseline import BaselineDeviation, compute_baselines  # noqa: E402
from models.community_detection.louvain_detector import (
    Community,
    LouvainClusterDetector,
)  # noqa: E402
from models.device.device_profiler import DeviceProfiler, DeviceTrustResult  # noqa: E402
from models.explainability.shap_explainer import SHAPAlertExplainer  # noqa: E402
from models.gnn.lightweight_scorer import LightweightScorer  # noqa: E402
from models.semantics.transaction_analyzer import (
    SemanticsResult,
    TransactionSemanticsAnalyzer,
)  # noqa: E402
from models.temporal.markov_state import MarkovStateResult, MarkovStateScorer  # noqa: E402
from models.temporal_weighting.smurf_weighting import (
    AccountScore,
    score_transaction_batch,
)  # noqa: E402

# A node that receives at least this many times what it sends is an AGGREGATOR
AGGREGATOR_RECEIVE_RATIO = 3.0

# ── Data models ───────────────────────────────────────────────────────────


@dataclass
class AlertNode:
    account_id: str
    role: str  # inferred from flow: SOURCE | MULE | AGGREGATOR | UNKNOWN
    smurf_score: float
    bank: str
    city: str
    account_age_days: int
    kyc_status: str
    upi_id: str
    betweenness: float = 0.0  # betweenness centrality (0-1, higher = more bridging)
    pagerank: float = 0.0  # PageRank score (higher = more influential)
    baseline_deviation: float = 0.0  # behavioral deviation from historical baseline
    device_trust_score: float = 0.0  # device profiling risk (0=trusted, 1=untrusted)
    semantics_score: float = 0.0  # transaction semantics risk (0-1)
    markov_transition_score: float = 0.0  # Markov state transition risk (0-1)
    anomaly_score: float = 0.0  # PyOD cold-start anomaly probability (0-1)
    # CBS behavioral features (populated from MuleCSVAdapter)
    pass_through_ratio: float = 0.0
    debit_credit_ratio: float = 0.0
    negative_balance_count: int = 0
    credit_count: int = 0
    debit_count: int = 0


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
    severity: str  # CRITICAL | HIGH | MEDIUM
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
    status: str = "OPEN"  # OPEN | UNDER_REVIEW | RESOLVED | FALSE_POSITIVE | NO_FURTHER_ACTION | SUSPICION_CONFIRMED_ESCALATED | STR_FILED
    investigator_notes: str = ""
    gnn_score: Optional[float] = None
    anomaly_score: Optional[float] = None
    genai_triage: Optional[Dict] = None
    explanation: Optional[Dict] = None
    narrative: Optional[Dict] = None
    mule_classification: Optional[Dict] = None
    shap_explanation: Optional[Dict] = None
    regulatory_report: Optional[Dict] = None
    model_version: str = "unversioned"
    rule_version: str = "unversioned"
    # Queue ranking: risk weighted by the evidence members carry themselves, and the share of members that carry any.
    rank_score: float = 0.0
    evidence_share: float = 0.0


# A member counts as carrying its own evidence at this smurf score (same level as the live scorer's gate).
MEMBER_EVIDENCE_MIN = 0.30


def case_priority(risk_score: float, member_smurf: List[float]) -> Tuple[float, float]:
    """Purity-weighted ranking: (risk x mean member smurf score, share of members with evidence).

    A community whose members show little individual evidence drops down the queue even when its
    graph shape alone pushes the risk score to the cap. Uses no labels (05-evaluation.md 7.4).
    """
    if not member_smurf:
        return 0.0, 0.0
    mean = sum(member_smurf) / len(member_smurf)
    share = sum(1 for s in member_smurf if s >= MEMBER_EVIDENCE_MIN) / len(member_smurf)
    return risk_score * mean, share


# ── Rule engine ───────────────────────────────────────────────────────────


class RuleEngine:
    """
    Fast, deterministic rules applied before ML scoring.
    Behavioral patterns aligned with RBI/RBIH MuleHunter framework. R07-R11, R16 and R19 were
    removed after firing more on genuine accounts than on mules (scripts/evaluation/evaluate_rules.py).
    """

    RULES = [
        # ── Original 4 rules ────────────────────────────────────────────
        (
            "R01",
            "Account age < 7 days",
            lambda a, txns: a.get("account_age_days", 999) < 7,
        ),
        (
            "R02",
            "> 20 transactions in 24h",
            lambda a, txns: _count_outgoing(a, txns) > 20,
        ),
        (
            "R03",
            "KYC pending with high volume",
            lambda a, txns: a.get("kyc_status") == "PENDING" and _count_outgoing(a, txns) > 5,
        ),
        (
            "R04",
            "Amounts structured below ₹50k threshold",
            lambda a, txns: _all_near_ceiling(a["account_id"], txns),
        ),
        # ── MuleHunter-aligned behavioral patterns ──────────────────────
        (
            "R05",
            "Dormant account suddenly activated",
            lambda a, txns: (
                a.get("account_age_days", 0) > 180 and a.get("avg_monthly_txn", 0) < 3 and _count_outgoing(a, txns) > 8
            ),
        ),
        (
            "R06",
            "Same-day credit-debit (pass-through)",
            lambda a, txns: _same_day_credit_debit(a["account_id"], txns),
        ),
        (
            "R12",
            "Identical amounts to multiple recipients",
            lambda a, txns: _identical_amounts(a["account_id"], txns),
        ),
        (
            "R13",
            "Geographic anomaly — multi-city in 24h",
            lambda a, txns: _geographic_anomaly(a["account_id"], txns),
        ),
        (
            "R14",
            "Split transaction pattern (< ₹10k each, > ₹1L total)",
            lambda a, txns: _split_transactions(a["account_id"], txns),
        ),
        ("R15", "High-risk UPI handle pattern", lambda a, txns: _high_risk_upi(a)),
        (
            "R17",
            "Velocity acceleration — txn rate doubling",
            lambda a, txns: _velocity_acceleration(a["account_id"], txns),
        ),
        (
            "R18",
            "Shared device across multiple accounts",
            lambda a, txns: _shared_device(a["account_id"], txns),
        ),
        # ── 72-hour early detection (BioCatch research) ──────────────
        (
            "R20",
            "72-hour behavioral anomaly — high activity within 3 days of opening",
            lambda a, txns: _seventy_two_hour_anomaly(a, txns),
        ),
    ]

    def evaluate(self, accounts: List[Dict], transactions: List[Dict]) -> Dict[str, List[str]]:
        results: Dict[str, List[str]] = {}
        for acc in accounts:
            hits = [f"{code}: {desc}" for code, desc, fn in self.RULES if fn(acc, transactions)]
            if hits:
                results[acc["account_id"]] = hits
        return results


# ── Rule helper functions ─────────────────────────────────────────────────


def _count_outgoing(a: Dict, txns: List[Dict]) -> int:
    return sum(1 for t in txns if t["from_account"] == a["account_id"])


def _all_near_ceiling(account_id: str, transactions: List[Dict]) -> bool:
    amounts = [
        t["amount"]
        for t in transactions
        if t["from_account"] == account_id and STRUCTURED_AMOUNT_LOWER <= float(t["amount"]) < STRUCTURED_AMOUNT_UPPER
    ]
    total = sum(1 for t in transactions if t["from_account"] == account_id)
    return total > STRUCTURED_MIN_TXNS and len(amounts) / max(total, 1) > STRUCTURED_RATIO_THRESHOLD


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












def _identical_amounts(account_id: str, txns: List[Dict]) -> bool:
    """Same exact amount sent to multiple different recipients."""
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
    small = [a for a in outgoing if a < SPLIT_TXN_AMOUNT_UPPER]
    return len(small) >= SPLIT_TXN_MIN_COUNT and sum(small) >= SPLIT_TXN_TOTAL_THRESHOLD


def _high_risk_upi(a: Dict) -> bool:
    """UPI handle associated with known fraud patterns."""
    upi = a.get("upi_id", "")
    # Random/disposable UPI handles with numeric-heavy patterns
    if not upi:
        return False
    digit_ratio = sum(1 for c in upi if c.isdigit()) / max(len(upi), 1)
    return digit_ratio > UPI_DIGIT_RATIO_THRESHOLD and len(upi) > UPI_MIN_LENGTH




def _velocity_acceleration(account_id: str, txns: List[Dict]) -> bool:
    """Transaction rate more than doubles compared to historical average."""
    avg_monthly = 10  # default
    current_count = sum(1 for t in txns if t["from_account"] == account_id)
    return current_count > avg_monthly * 2


def _shared_device(account_id: str, txns: List[Dict]) -> bool:
    """Multiple accounts using the same device_id."""
    my_devices = set(t.get("device_id", "") for t in txns if t["from_account"] == account_id and t.get("device_id"))
    if not my_devices:
        return False
    for dev in my_devices:
        other_accounts = set(
            t["from_account"] for t in txns if t.get("device_id") == dev and t["from_account"] != account_id
        )
        if other_accounts:
            return True
    return False




def _seventy_two_hour_anomaly(a: Dict, txns: List[Dict]) -> bool:
    """
    BioCatch-inspired: 48% of mule accounts show behavioral inconsistencies
    within 72 hours of account opening. Flag accounts <3 days old with
    abnormally high outgoing activity.
    """
    age_days = a.get("account_age_days", 999)
    if age_days > EARLY_ANOMALY_AGE_DAYS:
        return False
    outgoing = sum(1 for t in txns if t["from_account"] == a["account_id"])
    outgoing_amount = sum(float(t["amount"]) for t in txns if t["from_account"] == a["account_id"])
    # Account <72h old with 5+ outgoing txns or >₹1L outgoing volume
    return outgoing >= EARLY_ANOMALY_MIN_TXNS or outgoing_amount >= EARLY_ANOMALY_MIN_AMOUNT


# ── GNN scorer (lazy import, optional) ───────────────────────────────────


def _try_load_gnn_scorer(model_path: str = None):
    """Attempt to load the GNN scorer; returns None if unavailable."""
    try:
        from models.gnn.gnn_model import GNNScorer

        scorer = GNNScorer(model_path=model_path)
        return scorer
    except Exception:
        return None


# ── Detection pipeline ────────────────────────────────────────────────────


def _infer_role(account_id: str, flows: List[Dict]) -> str:
    """Structural role from observed money flow inside the ring.

    Never reads generator or analyst labels: SOURCE only sends, AGGREGATOR
    mostly receives, MULE both receives and forwards.
    """
    sent = sum(float(t["amount"]) for t in flows if t["from_account"] == account_id)
    received = sum(float(t["amount"]) for t in flows if t["to_account"] == account_id)
    if sent == 0 and received == 0:
        return "UNKNOWN"
    if received == 0:
        return "SOURCE"
    if received >= AGGREGATOR_RECEIVE_RATIO * sent:
        return "AGGREGATOR"
    return "MULE"


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

    # ── Severity thresholds ──────────────────────────────────────────────
    SEVERITY_CRITICAL_THRESHOLD = 0.80  # risk_score >= this → CRITICAL
    SEVERITY_HIGH_THRESHOLD = 0.60  # risk_score >= this → HIGH (else MEDIUM)

    # ── GenAI triage band ────────────────────────────────────────────────
    # Only uncertain alerts within this risk range are sent to LLM triage
    GENAI_TRIAGE_LOWER = 0.40
    GENAI_TRIAGE_UPPER = 0.65

    # ── Smurf / GNN aggregation weights ──────────────────────────────────
    # Blend of max + mean: cluster risk is driven by highest-scoring member,
    # not diluted by low-scoring mules.
    AGG_MAX_WEIGHT = 0.6  # weight for max score
    AGG_MEAN_WEIGHT = 0.4  # weight for mean score

    # ── Centrality boost parameters ──────────────────────────────────────
    BETWEENNESS_MULTIPLIER = 0.4  # scale factor for betweenness
    BETWEENNESS_BOOST_CAP = 0.08  # max boost from betweenness centrality
    PAGERANK_MULTIPLIER = 4  # scale factor for PageRank
    PAGERANK_BOOST_CAP = 0.04  # max boost from PageRank

    # ── Behavioral baseline boost ────────────────────────────────────────
    BASELINE_DEVIATION_MULTIPLIER = 0.1  # scale factor for deviation score
    BASELINE_BOOST_CAP = 0.06  # max boost from baseline deviation

    # ── Transaction semantics boost ──────────────────────────────────────
    SEMANTICS_MULTIPLIER = 0.1  # scale factor for semantics score
    SEMANTICS_BOOST_CAP = 0.05  # max boost from semantics analysis

    # ── Device trust boost ───────────────────────────────────────────────
    DEVICE_MULTIPLIER = 0.12  # scale factor for device trust score
    DEVICE_BOOST_CAP = 0.06  # max boost from device profiling

    # ── Markov transition boost ──────────────────────────────────────────
    MARKOV_MULTIPLIER = 0.15  # scale factor for Markov transition score
    MARKOV_BOOST_CAP = 0.08  # max boost from temporal state transitions

    # ── Structural risk amplifiers ───────────────────────────────────────
    # Large clusters with many reason codes are more suspicious
    LARGE_CLUSTER_SIZE = 12  # member count for large cluster
    LARGE_CLUSTER_CODES = 6  # reason code count for large cluster
    LARGE_CLUSTER_BOOST = 0.10  # risk increment for large clusters

    MEDIUM_CLUSTER_SIZE = 10  # member count for medium cluster
    MEDIUM_CLUSTER_CODES = 5  # reason code count for medium cluster
    MEDIUM_CLUSTER_BOOST = 0.05  # risk increment for medium clusters

    # Shared device fingerprint amplifiers
    SHARED_DEVICES_HIGH = 3  # device count for high amplification
    SHARED_DEVICES_HIGH_BOOST = 0.08  # risk increment for 3+ shared devices
    SHARED_DEVICES_LOW = 2  # device count for low amplification
    SHARED_DEVICES_LOW_BOOST = 0.04  # risk increment for 2+ shared devices

    # ── Risk score bounds ────────────────────────────────────────────────
    RISK_SCORE_CAP = 0.99  # maximum risk score

    # ── Confidence calculation ───────────────────────────────────────────
    CONFIDENCE_CODE_FACTOR = 0.05  # per-unique-reason-code confidence bump
    CONFIDENCE_CAP = 1.0  # maximum confidence score

    # ── Reason code limits ───────────────────────────────────────────────
    MAX_REASON_CODES = 15  # max deduplicated reason codes per alert

    def __init__(
        self,
        smurf_threshold: Optional[float] = None,
        suspicion_threshold: Optional[float] = None,
        gnn_model_path: Optional[str] = None,
        genai_service=None,
        model_version: str = "unvalidated-dev",
        rule_version: str = "rules-2026.2",
        device_profiler: Optional[DeviceProfiler] = None,
        anomaly_scorer: Optional[UnsupervisedAccountScorer] = None,
    ):
        self.rule_engine = RuleEngine()
        self.cluster_detector = LouvainClusterDetector()
        self._gnn_model_path = gnn_model_path
        self._gnn_scorer = _try_load_gnn_scorer(model_path=gnn_model_path)
        self._gnn_available = self._gnn_scorer is not None
        self._lightweight_scorer = LightweightScorer()
        self._genai_service = genai_service
        self._model_version = model_version
        self._rule_version = rule_version
        self._semantics_analyzer = TransactionSemanticsAnalyzer()
        self._device_profiler = device_profiler or DeviceProfiler()
        self._anomaly_scorer = anomaly_scorer or UnsupervisedAccountScorer()
        self._markov_scorer = MarkovStateScorer()
        self._shap_explainer = SHAPAlertExplainer()

        # Threshold overrides from feedback engine
        self._smurf_threshold = smurf_threshold
        self._suspicion_threshold = suspicion_threshold

    def run(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> List[Alert]:
        start = datetime.now(timezone.utc)

        # Layer 1: rules
        rule_hits = self.rule_engine.evaluate(accounts, transactions)

        # Layer 2: smurf-weighting
        smurf_scores: Dict[str, AccountScore] = score_transaction_batch(transactions)

        # Layer 2b: behavioral baseline comparison
        baselines = compute_baselines(accounts, transactions)

        # Layer 2c: transaction semantics analysis
        semantics = self._semantics_analyzer.analyze_batch(accounts, transactions)

        # Layer 2d: device profiling
        device_results = self._profile_devices(accounts, transactions)

        # Layer 2e: Markov state transition scoring
        markov_results = self._markov_scorer.score_batch(accounts, transactions)

        # Layer 3: community detection
        communities = self.cluster_detector.detect_clusters(transactions, accounts)

        # Layer 3b: centrality scoring (betweenness + PageRank)
        centrality = self.cluster_detector.compute_centrality()

        # Layer 3c: label-free cold-start anomaly scoring. This remains a
        # supporting signal and never creates an adverse decision on its own.
        anomaly_predictions = self._anomaly_scorer.score(
            accounts,
            transactions,
            smurf_scores,
            centrality,
            baselines,
        )

        # Layer 4: GNN scoring (optional)
        gnn_predictions = {}
        if self._gnn_available and self._gnn_scorer is not None:
            try:
                if self._gnn_scorer.is_trained:
                    # Fast path: model already trained/loaded
                    preds = self._gnn_scorer.predict(
                        accounts,
                        transactions,
                        smurf_scores,
                    )
                else:
                    # Train on this data (stratified split), save weights
                    preds, metrics = self._gnn_scorer.train_and_predict(
                        accounts,
                        transactions,
                        smurf_scores,
                    )
                    logger.info(
                        "GNN trained: %d epochs, final_loss=%.4f, train_acc=%.3f",
                        metrics.epochs,
                        metrics.final_loss,
                        metrics.train_accuracy,
                    )
                gnn_predictions = {p.account_id: p for p in preds}
            except Exception as exc:
                logger.warning("GNN scoring failed (falling back): %s", exc)

        # Layer 4b: Lightweight scorer fallback (when GNN unavailable)
        if not gnn_predictions and self._lightweight_scorer is not None:
            try:
                lw_preds = self._lightweight_scorer.predict(
                    accounts,
                    transactions,
                    smurf_scores,
                    centrality,
                    baselines,
                )
                if lw_preds:
                    gnn_predictions = {p.account_id: p for p in lw_preds}
                    logger.info("Lightweight scorer: %d predictions", len(lw_preds))
            except Exception as exc:
                logger.warning("Lightweight scorer failed: %s", exc)

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
                semantics,
                device_results,
                markov_results,
                anomaly_predictions,
            )
            alerts.append(alert)

        # Layer 5: GenAI triage — LLM reviews uncertain alerts
        if self._genai_service is not None:
            for alert in alerts:
                if self.GENAI_TRIAGE_LOWER <= alert.risk_score <= self.GENAI_TRIAGE_UPPER:
                    try:
                        triage = self._genai_service.triage_cluster(
                            alert_data={
                                "cluster_id": alert.cluster_id,
                                "risk_score": alert.risk_score,
                                "account_count": alert.account_count,
                                "txn_count": alert.txn_count,
                                "total_amount": alert.total_amount,
                                "reason_codes": alert.reason_codes,
                                "shared_devices": alert.shared_devices,
                                "nodes": [vars(n) for n in alert.nodes],
                                "edges": [vars(e) for e in alert.edges],
                            }
                        )
                        # Advisory only: the LLM opinion is shown to the analyst and never changes risk or rank.
                        alert.genai_triage = triage.to_dict()
                    except Exception as exc:
                        logger.warning(
                            "GenAI triage failed for %s: %s",
                            alert.alert_id,
                            exc,
                        )

        # Layer 6: Explainability — generate explanations for each alert
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
                    "anomaly_score": alert.anomaly_score,
                }
                explanation = explain_alert(alert_dict, smurf_scores)
                alert.explanation = explanation.to_dict()
            except Exception as exc:
                logger.warning("Explainability failed for %s: %s", alert.alert_id, exc)

            # SHAP-based explanation (RBI FREE-AI compliant)
            try:
                shap_explanation = self._shap_explainer.explain_alert(alert_dict, smurf_scores)
                alert.shap_explanation = shap_explanation.to_dict()
                alert.regulatory_report = self._shap_explainer.generate_regulatory_report(shap_explanation)
            except Exception as exc:
                logger.warning("SHAP explanation failed for %s: %s", alert.alert_id, exc)

        # Layer 7: Mule type classification + narrative generation
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
                    "anomaly_score": alert.anomaly_score,
                    "explanation": alert.explanation or {},
                }
                classification = classify_cluster(alert_dict, transactions)
                alert.mule_classification = classification

                narrative = generate_narrative(alert_dict, classification)
                alert.narrative = narrative.to_dict()
            except Exception as exc:
                logger.warning("Classification/narrative failed for %s: %s", alert.alert_id, exc)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        gnn_status = "with GNN" if gnn_predictions else "without GNN"
        logger.info(
            "Detection pipeline (%s): %d txns -> %d alerts in %.2fs",
            gnn_status,
            len(transactions),
            len(flagged_communities),
            elapsed,
        )

        return sorted(alerts, key=lambda a: -a.rank_score)

    def _profile_devices(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
    ) -> Dict[str, DeviceTrustResult]:
        """Record device events from transactions and compute trust scores."""
        results = {}
        try:
            for t in transactions:
                device_id = t.get("device_id", "")
                if not device_id:
                    continue
                self._device_profiler.record_device_event(
                    account_id=t["from_account"],
                    device_id=device_id,
                )
            for acc in accounts:
                acc_id = acc["account_id"]
                results[acc_id] = self._device_profiler.compute_trust(acc_id)
        except Exception as exc:
            logger.warning("Device profiling failed: %s", exc)
        return results

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
        semantics: Dict[str, SemanticsResult] = None,
        device_results: Dict[str, DeviceTrustResult] = None,
        markov_results: Dict[str, MarkovStateResult] = None,
        anomaly_predictions: Dict[str, AnomalyPrediction] = None,
    ) -> Alert:
        members = community.accounts

        # Filter transactions within this community
        community_txns = [t for t in transactions if t["from_account"] in members or t["to_account"] in members]

        # Build nodes
        centrality = centrality or {}
        baselines = baselines or {}
        semantics = semantics or {}
        device_results = device_results or {}
        markov_results = markov_results or {}
        anomaly_predictions = anomaly_predictions or {}
        nodes = []
        for acc_id in members:
            acc = acc_map.get(acc_id, {})
            ss = smurf_scores.get(acc_id)
            cs = centrality.get(acc_id, {})
            bl = baselines.get(acc_id)
            sem = semantics.get(acc_id)
            dev = device_results.get(acc_id)
            mk = markov_results.get(acc_id)
            anomaly = anomaly_predictions.get(acc_id)
            nodes.append(
                AlertNode(
                    account_id=acc_id,
                    role=_infer_role(acc_id, community_txns),
                    smurf_score=ss.smurf_score if ss else 0.0,
                    bank=acc.get("bank", ""),
                    city=acc.get("city", ""),
                    account_age_days=acc.get("account_age_days", 0),
                    kyc_status=acc.get("kyc_status", "UNKNOWN"),
                    upi_id=acc.get("upi_id", ""),
                    betweenness=cs.get("betweenness", 0.0),
                    pagerank=cs.get("pagerank", 0.0),
                    baseline_deviation=bl.composite_score if bl else 0.0,
                    device_trust_score=dev.device_trust_score if dev else 0.0,
                    semantics_score=sem.composite_score if sem else 0.0,
                    markov_transition_score=mk.transition_score if mk else 0.0,
                    anomaly_score=anomaly.anomaly_score if anomaly else 0.0,
                    pass_through_ratio=acc.get("pass_through_ratio", 0.0),
                    debit_credit_ratio=acc.get("debit_credit_ratio", 0.0),
                    negative_balance_count=acc.get("negative_balance_count", 0),
                    credit_count=acc.get("credit_count", 0),
                    debit_count=acc.get("debit_count", 0),
                )
            )

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
                    pattern="OBSERVED",
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
            sem = semantics.get(acc_id)
            if sem:
                all_codes.extend(sem.reason_codes)
            dev = device_results.get(acc_id)
            if dev:
                all_codes.extend(dev.reason_codes)
            mk = markov_results.get(acc_id)
            if mk:
                all_codes.extend(mk.reason_codes)
            anomaly = anomaly_predictions.get(acc_id)
            if anomaly and anomaly.is_anomaly:
                all_codes.append(f"AD01: PyOD ECOD peer-group anomaly (score={anomaly.anomaly_score:.2f})")
        unique_codes = list(dict.fromkeys(all_codes))[: self.MAX_REASON_CODES]

        # Composite risk score with optional GNN layer
        # Use blend of max + avg smurf scores: cluster risk is driven by
        # the highest-scoring member (SOURCE), not diluted by low-scoring mules
        member_smurf = [smurf_scores[a].smurf_score for a in members if a in smurf_scores]
        if member_smurf:
            max_smurf = max(member_smurf)
            mean_smurf = sum(member_smurf) / len(member_smurf)
            avg_smurf = self.AGG_MAX_WEIGHT * max_smurf + self.AGG_MEAN_WEIGHT * mean_smurf
        else:
            avg_smurf = 0.0

        avg_gnn = None
        if gnn_predictions:
            gnn_scores = [gnn_predictions[a].mule_probability for a in members if a in gnn_predictions]
            if gnn_scores:
                max_gnn = max(gnn_scores)
                mean_gnn = sum(gnn_scores) / len(gnn_scores)
                avg_gnn = self.AGG_MAX_WEIGHT * max_gnn + self.AGG_MEAN_WEIGHT * mean_gnn

        # Centrality amplifier: accounts with high betweenness are network
        # bridges (money laundering bottlenecks); high PageRank means they
        # receive flow from many paths.  max() captures the most critical node.
        member_betweenness = [centrality.get(a, {}).get("betweenness", 0) for a in members]
        member_pagerank = [centrality.get(a, {}).get("pagerank", 0) for a in members]
        max_betweenness = max(member_betweenness) if member_betweenness else 0
        max_pagerank = max(member_pagerank) if member_pagerank else 0
        # Centrality boost from betweenness + PageRank
        centrality_boost = min(max_betweenness * self.BETWEENNESS_MULTIPLIER, self.BETWEENNESS_BOOST_CAP) + min(
            max_pagerank * self.PAGERANK_MULTIPLIER, self.PAGERANK_BOOST_CAP
        )

        # Behavioral baseline boost: up to +0.06 from deviation
        member_baselines = [baselines.get(a, BaselineDeviation(a)).composite_score for a in members]
        max_baseline_dev = max(member_baselines) if member_baselines else 0
        baseline_boost = min(
            max_baseline_dev * self.BASELINE_DEVIATION_MULTIPLIER,
            self.BASELINE_BOOST_CAP,
        )

        # Semantics boost: up to +0.05 from transaction semantics
        _empty_sem = SemanticsResult("", 0.0, 0.0, 0.0, 0.0, 0.0, ())
        member_semantics = [semantics.get(a, _empty_sem).composite_score for a in members]
        max_semantics = max(member_semantics) if member_semantics else 0
        semantics_boost = min(max_semantics * self.SEMANTICS_MULTIPLIER, self.SEMANTICS_BOOST_CAP)

        # Device trust boost: up to +0.06 from device profiling
        _empty_dev = DeviceTrustResult("", 0.0, 0, 0, (), ())
        member_device = [device_results.get(a, _empty_dev).device_trust_score for a in members]
        max_device = max(member_device) if member_device else 0
        device_boost = min(max_device * self.DEVICE_MULTIPLIER, self.DEVICE_BOOST_CAP)

        # Markov transition boost: up to +0.08 from temporal state transitions
        _empty_mk = MarkovStateResult("", "DORMANT", (), 0.0, 0.0, ())
        member_markov = [markov_results.get(a, _empty_mk).transition_score for a in members]
        max_markov = max(member_markov) if member_markov else 0
        markov_boost = min(max_markov * self.MARKOV_MULTIPLIER, self.MARKOV_BOOST_CAP)

        # PyOD is deliberately capped below the graph/behavioral layers. It
        # improves prioritisation without becoming an opaque decision maker.
        member_anomalies = [
            anomaly_predictions[a].anomaly_score
            for a in members
            if a in anomaly_predictions and anomaly_predictions[a].is_anomaly
        ]
        max_anomaly = max(member_anomalies) if member_anomalies else 0.0
        anomaly_boost = min(max_anomaly * 0.06, 0.06)

        if avg_gnn is not None:
            # 4-layer scoring: 50% Louvain + 30% Smurf + 20% GNN + boosts
            risk_score = (
                self.DEFAULT_LOUVAIN_WEIGHT * community.suspicion_score
                + self.DEFAULT_SMURF_WEIGHT * avg_smurf
                + self.DEFAULT_GNN_WEIGHT * avg_gnn
                + centrality_boost
                + baseline_boost
                + semantics_boost
                + device_boost
                + markov_boost
                + anomaly_boost
            )
        else:
            # 3-layer fallback: 60% Louvain + 40% Smurf + boosts
            risk_score = (
                self.FALLBACK_LOUVAIN_WEIGHT * community.suspicion_score
                + self.FALLBACK_SMURF_WEIGHT * avg_smurf
                + centrality_boost
                + baseline_boost
                + semantics_boost
                + device_boost
                + markov_boost
                + anomaly_boost
            )

        # Structural risk amplifiers
        # Large clusters with many reason codes are more suspicious
        if len(members) >= self.LARGE_CLUSTER_SIZE and len(unique_codes) >= self.LARGE_CLUSTER_CODES:
            risk_score += self.LARGE_CLUSTER_BOOST
        elif len(members) >= self.MEDIUM_CLUSTER_SIZE and len(unique_codes) >= self.MEDIUM_CLUSTER_CODES:
            risk_score += self.MEDIUM_CLUSTER_BOOST

        # Multiple shared fingerprints amplify risk
        if len(community.shared_devices) >= self.SHARED_DEVICES_HIGH:
            risk_score += self.SHARED_DEVICES_HIGH_BOOST
        elif len(community.shared_devices) >= self.SHARED_DEVICES_LOW:
            risk_score += self.SHARED_DEVICES_LOW_BOOST

        risk_score = min(risk_score, self.RISK_SCORE_CAP)

        confidence = min(
            risk_score + self.CONFIDENCE_CODE_FACTOR * len(unique_codes),
            self.CONFIDENCE_CAP,
        )

        total_amount = sum(float(t["amount"]) for t in community_txns)
        rank_score, evidence_share = case_priority(risk_score, member_smurf)

        severity = (
            "CRITICAL"
            if risk_score >= self.SEVERITY_CRITICAL_THRESHOLD
            else "HIGH"
            if risk_score >= self.SEVERITY_HIGH_THRESHOLD
            else "MEDIUM"
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
            created_at=datetime.now(timezone.utc).isoformat(),
            gnn_score=round(avg_gnn, 3) if avg_gnn is not None else None,
            anomaly_score=round(max_anomaly, 3) if member_anomalies else None,
            model_version=self._model_version,
            rule_version=self._rule_version,
            rank_score=round(rank_score, 3),
            evidence_share=round(evidence_share, 3),
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
        print(
            f"  [{a.severity}] {a.alert_id}  score={a.risk_score:.3f}{gnn_str}  "
            f"accounts={a.account_count}  amount=₹{a.total_amount:,.0f}"
        )
        for rc in a.reason_codes[:3]:
            print(f"    {rc}")
