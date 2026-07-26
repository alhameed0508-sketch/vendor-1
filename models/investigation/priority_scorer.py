"""
Alert Priority Scorer — ML-based scoring for investigation queue
prioritization.

Composite scoring from risk, amount, network centrality, evidence
diversity, and time sensitivity.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
from dataclasses import dataclass
from typing import Dict, List

# -- Priority component weights (must sum to 1.0) -----------------------------
WEIGHT_RISK_SCORE = 0.30          # Direct risk score from the alert
WEIGHT_AMOUNT_FACTOR = 0.20       # Log-scaled transaction amount
WEIGHT_NETWORK_CENTRALITY = 0.20  # Max betweenness centrality from nodes
WEIGHT_EVIDENCE_DIVERSITY = 0.15  # Unique reason code prefixes / 10
WEIGHT_TIME_SENSITIVITY = 0.15    # Newer alerts + new accounts boost

# -- SAR filing base probabilities by severity --------------------------------
SAR_BASE_PROBABILITY = {
    "CRITICAL": 0.90,
    "HIGH": 0.60,
    "MEDIUM": 0.30,
    "LOW": 0.10,
}
# Default SAR probability when severity is unrecognized
SAR_DEFAULT_PROBABILITY = 0.10


@dataclass(frozen=True)
class AlertPriorityResult:
    """Immutable priority scoring result for a single alert."""

    alert_id: str
    priority_score: float  # 0.0 - 1.0
    sar_filing_probability: float  # probability of SAR filing
    investigation_complexity: str  # "HIGH", "MEDIUM", "LOW"
    estimated_priority_rank: int
    score_breakdown: Dict[str, float]

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "priority_score": round(self.priority_score, 4),
            "sar_filing_probability": round(self.sar_filing_probability, 4),
            "investigation_complexity": self.investigation_complexity,
            "estimated_priority_rank": self.estimated_priority_rank,
            "score_breakdown": {
                k: round(v, 4) for k, v in self.score_breakdown.items()
            },
        }


class AlertPriorityScorer:
    """Scores alerts for investigation queue prioritization.

    Composite score is a weighted sum of five components:
    - risk_score: direct from alert (weight 0.30)
    - amount_factor: log-scaled amount, capped at 1.0 for >10L (weight 0.20)
    - network_centrality: max betweenness from nodes (weight 0.20)
    - evidence_diversity: unique reason code prefixes / 10 (weight 0.15)
    - time_sensitivity: newer alerts + new accounts get boost (weight 0.15)
    """

    WEIGHTS: Dict[str, float] = {
        "risk_score": WEIGHT_RISK_SCORE,
        "amount_factor": WEIGHT_AMOUNT_FACTOR,
        "network_centrality": WEIGHT_NETWORK_CENTRALITY,
        "evidence_diversity": WEIGHT_EVIDENCE_DIVERSITY,
        "time_sensitivity": WEIGHT_TIME_SENSITIVITY,
    }

    # ₹10 Lakhs = 1,000,000
    AMOUNT_CAP_INR = 1_000_000.0

    def score_alert(self, alert_data: Dict) -> AlertPriorityResult:
        """Score a single alert for priority (rank = 1)."""
        breakdown = self._compute_breakdown(alert_data)
        priority_score = sum(
            self.WEIGHTS[k] * breakdown[k] for k in self.WEIGHTS
        )
        priority_score = max(0.0, min(1.0, priority_score))

        sar_prob = self.predict_sar_likelihood(alert_data)
        complexity = self._assess_complexity(alert_data)

        return AlertPriorityResult(
            alert_id=alert_data.get("alert_id", "UNKNOWN"),
            priority_score=priority_score,
            sar_filing_probability=sar_prob,
            investigation_complexity=complexity,
            estimated_priority_rank=1,
            score_breakdown=breakdown,
        )

    def score_queue(self, alerts: List[Dict]) -> List[AlertPriorityResult]:
        """Score and sort a list of alerts by priority (descending)."""
        scored = []
        for alert in alerts:
            result = self.score_alert(alert)
            scored.append(result)

        # Sort by priority score descending
        scored.sort(key=lambda r: r.priority_score, reverse=True)

        # Assign ranks (1-based)
        ranked = []
        for idx, result in enumerate(scored):
            ranked.append(AlertPriorityResult(
                alert_id=result.alert_id,
                priority_score=result.priority_score,
                sar_filing_probability=result.sar_filing_probability,
                investigation_complexity=result.investigation_complexity,
                estimated_priority_rank=idx + 1,
                score_breakdown=result.score_breakdown,
            ))
        return ranked

    def predict_sar_likelihood(self, alert_data: Dict) -> float:
        """Predict probability that alert results in SAR filing.

        Base probability from severity:
        - CRITICAL: 0.9
        - HIGH: 0.6
        - MEDIUM: 0.3
        - LOW / other: 0.1

        Adjusted upward by evidence count (reason codes).
        """
        severity = alert_data.get("severity", "").upper()
        base = SAR_BASE_PROBABILITY.get(severity, SAR_DEFAULT_PROBABILITY)

        # Adjust by evidence count
        reason_codes = alert_data.get("reason_codes", [])
        evidence_boost = min(len(reason_codes) * 0.02, 0.10)

        return min(1.0, base + evidence_boost)

    # ── Private scoring components ───────────────────────────────────────

    def _compute_breakdown(self, alert_data: Dict) -> Dict[str, float]:
        """Compute individual score components (each 0.0 - 1.0)."""
        return {
            "risk_score": self._score_risk(alert_data),
            "amount_factor": self._score_amount(alert_data),
            "network_centrality": self._score_centrality(alert_data),
            "evidence_diversity": self._score_evidence_diversity(alert_data),
            "time_sensitivity": self._score_time_sensitivity(alert_data),
        }

    @staticmethod
    def _score_risk(alert_data: Dict) -> float:
        """Direct risk score from alert, clamped to [0, 1]."""
        raw = float(alert_data.get("risk_score", 0))
        return max(0.0, min(1.0, raw))

    def _score_amount(self, alert_data: Dict) -> float:
        """Log-scaled amount factor, capped at 1.0 for amounts > ₹10L."""
        amount = float(alert_data.get("total_amount", 0))
        if amount <= 0:
            return 0.0
        if amount >= self.AMOUNT_CAP_INR:
            return 1.0
        # Log scale: log(amount) / log(cap)
        return min(1.0, math.log1p(amount) / math.log1p(self.AMOUNT_CAP_INR))

    @staticmethod
    def _score_centrality(alert_data: Dict) -> float:
        """Max betweenness centrality from nodes, clamped to [0, 1]."""
        nodes = alert_data.get("nodes", [])
        if not nodes:
            return 0.0
        max_betweenness = max(
            float(n.get("betweenness_centrality", 0)) for n in nodes
        )
        return max(0.0, min(1.0, max_betweenness))

    @staticmethod
    def _score_evidence_diversity(alert_data: Dict) -> float:
        """Count of unique reason code prefixes / 10, capped at 1.0."""
        reason_codes = alert_data.get("reason_codes", [])
        prefixes = set()
        for rc in reason_codes:
            # Extract prefix: "R01: ..." -> "R01", "Device shared..." -> "Device"
            prefix = rc.split(":")[0].strip() if ":" in rc else rc.split()[0] if rc else ""
            if prefix:
                prefixes.add(prefix)
        return min(1.0, len(prefixes) / 10.0)

    @staticmethod
    def _score_time_sensitivity(alert_data: Dict) -> float:
        """Newer alerts and accounts < 7 days old get higher scores."""
        nodes = alert_data.get("nodes", [])
        if not nodes:
            return 0.5  # Default mid-range

        # Check for new accounts (< 7 days)
        new_account_count = sum(
            1 for n in nodes
            if (n.get("account_age_days") or 999) < 7
        )
        total = len(nodes)

        # Proportion of new accounts (0 to 1)
        new_ratio = new_account_count / max(total, 1)

        # Boost: more new accounts = higher time sensitivity
        # Base 0.5 + up to 0.5 boost for all-new accounts
        return min(1.0, 0.5 + 0.5 * new_ratio)

    @staticmethod
    def _assess_complexity(alert_data: Dict) -> str:
        """Estimate investigation complexity based on alert characteristics."""
        node_count = alert_data.get("account_count", 0)
        if node_count == 0:
            node_count = len(alert_data.get("nodes", []))

        txn_count = alert_data.get("txn_count", 0)
        reason_count = len(alert_data.get("reason_codes", []))

        complexity_score = node_count + txn_count / 10 + reason_count

        if complexity_score > 15:
            return "HIGH"
        if complexity_score > 5:
            return "MEDIUM"
        return "LOW"
