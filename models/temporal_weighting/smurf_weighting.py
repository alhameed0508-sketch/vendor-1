"""
MuleCatch Temporal Smurf-Weighting Algorithm
============================================
Scores accounts and transaction clusters using temporal velocity,
amount distribution, and network fan-out patterns characteristic
of smurfing (structuring) fraud.

Key signals:
  1. Velocity burst  – many txns in short window
  2. Amount ceiling  – amounts cluster just below ₹50,000
  3. Fan-out ratio   – one account pushes to many others rapidly
  4. Temporal rhythm – regular interval spacing (bot-like)
  5. Rapid consolidation – mule-tier re-sends within N hours
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import math
import numpy as np


SMURF_CEILING = 50_000.0   # RBI flag threshold (INR)
SMURF_FLOOR   = 400.0      # minimum meaningful amount
HIGH_RISK_ZONE = 0.85      # amounts in this percentile of ceiling
VELOCITY_WINDOW_MINUTES = 60
CONSOLIDATION_WINDOW_HOURS = 6


@dataclass
class Transaction:
    txn_id: str
    from_account: str
    to_account: str
    amount: float
    timestamp: datetime
    device_id: str
    ip_address: str
    upi_id: str = ""
    pattern: str = "NORMAL"


@dataclass
class AccountScore:
    account_id: str
    smurf_score: float = 0.0
    velocity_score: float = 0.0
    amount_ceiling_score: float = 0.0
    fan_out_score: float = 0.0
    rhythm_score: float = 0.0
    consolidation_score: float = 0.0
    reason_codes: List[str] = field(default_factory=list)
    is_flagged: bool = False
    confidence: float = 0.0


class SmurfWeightingEngine:
    """
    Computes a composite smurf-risk score for each account
    based on its transaction history and network behavior.
    """

    WEIGHTS = {
        "velocity":      0.25,
        "amount_ceil":   0.25,
        "fan_out":       0.20,
        "rhythm":        0.15,
        "consolidation": 0.15,
    }
    FLAG_THRESHOLD = 0.55

    def score_account(
        self,
        account_id: str,
        outgoing: List[Transaction],
        incoming: List[Transaction],
    ) -> AccountScore:
        score = AccountScore(account_id=account_id)

        if not outgoing and not incoming:
            return score

        # ── 1. Velocity burst ─────────────────────────────────────────────
        score.velocity_score = self._velocity_score(outgoing)

        # ── 2. Amount ceiling proximity ───────────────────────────────────
        score.amount_ceiling_score = self._amount_ceiling_score(outgoing)

        # ── 3. Fan-out ratio ──────────────────────────────────────────────
        score.fan_out_score = self._fan_out_score(outgoing)

        # ── 4. Temporal rhythm (regular spacing = bot) ────────────────────
        score.rhythm_score = self._rhythm_score(outgoing)

        # ── 5. Rapid consolidation ────────────────────────────────────────
        score.consolidation_score = self._consolidation_score(outgoing, incoming)

        # ── Composite weighted score ──────────────────────────────────────
        w = self.WEIGHTS
        score.smurf_score = (
            w["velocity"]      * score.velocity_score +
            w["amount_ceil"]   * score.amount_ceiling_score +
            w["fan_out"]       * score.fan_out_score +
            w["rhythm"]        * score.rhythm_score +
            w["consolidation"] * score.consolidation_score
        )
        score.smurf_score = min(score.smurf_score, 1.0)
        score.is_flagged = score.smurf_score >= self.FLAG_THRESHOLD

        # ── Reason codes ──────────────────────────────────────────────────
        score.reason_codes = self._build_reason_codes(score)
        score.confidence = self._confidence(score, len(outgoing) + len(incoming))

        return score

    # ── individual scorers ────────────────────────────────────────────────────

    def _velocity_score(self, txns: List[Transaction]) -> float:
        if len(txns) < 2:
            return 0.0
        timestamps = sorted(t.timestamp for t in txns)
        windows = []
        for i, ts in enumerate(timestamps):
            window_end = ts + timedelta(minutes=VELOCITY_WINDOW_MINUTES)
            count = sum(1 for t2 in timestamps[i:] if t2 <= window_end)
            windows.append(count)
        max_in_window = max(windows)
        # >10 txns/hour is highly suspicious; normalise to 0-1
        return min(max_in_window / 12.0, 1.0)

    def _amount_ceiling_score(self, txns: List[Transaction]) -> float:
        if not txns:
            return 0.0
        amounts = [t.amount for t in txns if SMURF_FLOOR < t.amount < SMURF_CEILING]
        if not amounts:
            return 0.0
        danger_zone = SMURF_CEILING * HIGH_RISK_ZONE
        pct_in_zone = sum(1 for a in amounts if a >= danger_zone) / len(amounts)
        # also penalise suspiciously uniform amounts
        if len(amounts) > 3:
            cv = np.std(amounts) / (np.mean(amounts) + 1e-9)
            uniformity_bonus = max(0, 0.3 - cv)   # low CV = very uniform
        else:
            uniformity_bonus = 0.0
        return min(pct_in_zone + uniformity_bonus, 1.0)

    def _fan_out_score(self, txns: List[Transaction]) -> float:
        if not txns:
            return 0.0
        unique_recipients = len(set(t.to_account for t in txns))
        # >5 unique recipients in 24 h is suspicious
        return min(unique_recipients / 8.0, 1.0)

    def _rhythm_score(self, txns: List[Transaction]) -> float:
        if len(txns) < 4:
            return 0.0
        timestamps = sorted(t.timestamp for t in txns)
        gaps = [(timestamps[i+1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps)-1)]
        if not gaps:
            return 0.0
        mean_gap = np.mean(gaps)
        if mean_gap < 1:
            return 0.0
        cv = np.std(gaps) / mean_gap
        # low CV = very regular intervals -> bot-like behavior
        return max(0.0, 1.0 - cv)

    def _consolidation_score(
        self,
        outgoing: List[Transaction],
        incoming: List[Transaction],
    ) -> float:
        """
        Detects: receives money -> quickly re-sends all of it.
        Classic mule behavior.
        """
        if not outgoing or not incoming:
            return 0.0
        first_in  = min(t.timestamp for t in incoming)
        first_out = min(t.timestamp for t in outgoing)
        delta_hours = abs((first_out - first_in).total_seconds()) / 3600
        if delta_hours > CONSOLIDATION_WINDOW_HOURS:
            return 0.0
        in_sum  = sum(t.amount for t in incoming)
        out_sum = sum(t.amount for t in outgoing)
        if in_sum < 1:
            return 0.0
        ratio = min(out_sum / in_sum, 1.0)
        urgency = max(0, 1.0 - delta_hours / CONSOLIDATION_WINDOW_HOURS)
        return ratio * urgency

    def _build_reason_codes(self, s: AccountScore) -> List[str]:
        codes = []
        if s.velocity_score > 0.5:
            codes.append("RC01: High transaction velocity (burst pattern detected)")
        if s.amount_ceiling_score > 0.5:
            codes.append("RC02: Amounts clustered just below ₹50,000 threshold")
        if s.fan_out_score > 0.5:
            codes.append("RC03: High fan-out — funds dispersed to many accounts")
        if s.rhythm_score > 0.5:
            codes.append("RC04: Regular transaction spacing — potential automation")
        if s.consolidation_score > 0.5:
            codes.append("RC05: Rapid consolidation — received and re-sent within 6 hours")
        return codes

    def _confidence(self, s: AccountScore, n_txns: int) -> float:
        base = s.smurf_score
        evidence_boost = min(math.log(n_txns + 1) / math.log(20), 0.2)
        return min(base + evidence_boost, 1.0)


def score_transaction_batch(
    transactions: List[Dict],
) -> Dict[str, AccountScore]:
    """
    Convenience wrapper: accepts raw transaction dicts,
    groups by account, scores each.
    """
    from collections import defaultdict
    engine = SmurfWeightingEngine()

    # Group transactions
    out_map: Dict[str, List[Transaction]] = defaultdict(list)
    in_map:  Dict[str, List[Transaction]] = defaultdict(list)

    for t in transactions:
        ts = datetime.fromisoformat(t["timestamp"]) if isinstance(t["timestamp"], str) else t["timestamp"]
        txn = Transaction(
            txn_id=t["txn_id"],
            from_account=t["from_account"],
            to_account=t["to_account"],
            amount=float(t["amount"]),
            timestamp=ts,
            device_id=t.get("device_id", ""),
            ip_address=t.get("ip_address", ""),
            upi_id=t.get("upi_id", ""),
            pattern=t.get("pattern", "NORMAL"),
        )
        out_map[txn.from_account].append(txn)
        in_map[txn.to_account].append(txn)

    all_accounts = set(out_map.keys()) | set(in_map.keys())
    results = {}
    for acc_id in all_accounts:
        results[acc_id] = engine.score_account(
            acc_id, out_map.get(acc_id, []), in_map.get(acc_id, [])
        )
    return results


if __name__ == "__main__":
    # Quick self-test
    from data.synthetic.generator import build_full_dataset
    dataset = build_full_dataset(num_clusters=2, num_legit_accounts=20)
    scores = score_transaction_batch(dataset["transactions"])
    flagged = [s for s in scores.values() if s.is_flagged]
    print(f"Scored {len(scores)} accounts — {len(flagged)} flagged")
    for s in sorted(flagged, key=lambda x: -x.smurf_score)[:5]:
        print(f"  {s.account_id}  score={s.smurf_score:.3f}  codes={s.reason_codes}")