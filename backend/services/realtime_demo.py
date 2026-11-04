"""Helpers for seeding the real-time scorer with synthetic data (demo mode only)."""

from typing import Dict, List, Mapping, Sequence

# Ground-truth fields the generator emits. Detectors must never see them.
LABEL_FIELDS = frozenset({"role", "high_risk", "cluster_id", "is_suspicious", "pattern"})


def strip_labels(rows: Sequence[Mapping]) -> List[Dict]:
    """Return copies of ``rows`` without ground-truth label fields."""
    return [{k: v for k, v in row.items() if k not in LABEL_FIELDS} for row in rows]


# ── Live replay (demo mode only) ───────────────────────────────────────────────

import random  # noqa: E402
import time  # noqa: E402
from typing import Iterator, Optional  # noqa: E402

from services.realtime_scorer import RealtimeScorer  # noqa: E402

MULE_ROLES = frozenset({"SOURCE", "MULE", "AGGREGATOR"})
MAX_DELAY_S = 2.0  # clamp so a tiny `rate` cannot pin a worker thread
LIVE_EVERY_NTH = 5  # every 5th payment is "live"; the rest is trusted history
DEMO_CLUSTERS = 3
DEMO_LEGIT_ACCOUNTS = 60
DEMO_ADVERSARIAL = 10


class DemoReplay:
    """Replays held-out synthetic payments through its own scorer.

    Ground-truth roles stay in this object to keep the counters honest; they
    are never placed in an emitted event. Owns a private ``RealtimeScorer`` so
    replay commits never touch the public scorer's history.
    """

    def __init__(self, seed: int = 7):
        from data.synthetic.generator import build_adversarial_dataset

        # The generator reads the global PRNG: seed it, then restore so a replay
        # never changes random state for the rest of the process.
        saved_state = random.getstate()
        try:
            random.seed(seed)
            data = build_adversarial_dataset(
                num_clusters=DEMO_CLUSTERS,
                num_legit_accounts=DEMO_LEGIT_ACCOUNTS,
                num_adversarial=DEMO_ADVERSARIAL,
            )
        finally:
            random.setstate(saved_state)
        txns = sorted(data["transactions"], key=lambda t: t["timestamp"])
        self._live = [t for i, t in enumerate(txns) if i % LIVE_EVERY_NTH == 0]
        history = [t for i, t in enumerate(txns) if i % LIVE_EVERY_NTH]
        self._roles = {a["account_id"]: a.get("role", "") for a in data["accounts"]}
        self._scorer = RealtimeScorer(strip_labels(data["accounts"]), strip_labels(history))

    @property
    def live_size(self) -> int:
        return len(self._live)

    def _is_mule(self, account_id: str) -> bool:
        return self._roles.get(account_id) in MULE_ROLES

    def events(self, limit: Optional[int] = None, rate: float = 0.0) -> Iterator[dict]:
        """Yield one event per live payment, ``rate`` payments per second (0 = no delay)."""
        payments = flagged = mule_flagged = genuine_flagged = 0
        mule_amount = genuine_amount = 0.0  # rupees flagged, split by the hidden ground truth
        genuine_accounts: frozenset = frozenset()
        for raw in self._live[:limit]:
            payment = strip_labels([raw])[0]
            result = self._scorer.score_payment(payment, commit=True)
            both_mule = self._is_mule(raw["from_account"]) and self._is_mule(raw["to_account"])
            both_genuine = not self._is_mule(raw["from_account"]) and not self._is_mule(raw["to_account"])
            is_flag = result.decision == "FLAG"
            payments += 1
            flagged += is_flag
            mule_flagged += is_flag and both_mule
            genuine_flagged += is_flag and both_genuine
            mule_amount += payment["amount"] if is_flag and both_mule else 0.0
            genuine_amount += payment["amount"] if is_flag and both_genuine else 0.0
            if is_flag and both_genuine:
                genuine_accounts = genuine_accounts | {raw["from_account"], raw["to_account"]}
            yield {
                "payment": payment,
                "decision": result.decision,
                "case_id": result.case_id,
                "ring_members": list(result.ring_members),
                "risk_score": result.risk_score,
                "latency_ms": result.latency_ms,
                "reasons": list(result.reasons),
                "counters": {
                    "payments": payments,
                    "flagged": flagged,
                    "mule_payments_flagged": mule_flagged,
                    "genuine_payments_flagged": genuine_flagged,
                    "mule_amount_flagged": round(mule_amount, 2),
                    "genuine_amount_flagged": round(genuine_amount, 2),
                    "genuine_accounts_flagged": len(genuine_accounts),
                },
            }
            if rate > 0:
                time.sleep(min(1.0 / rate, MAX_DELAY_S))
