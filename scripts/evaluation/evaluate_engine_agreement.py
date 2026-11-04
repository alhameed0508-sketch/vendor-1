"""
Check that the batch pipeline and the per-payment scorer decide the same way.

Both engines ask ``ring_is_flaggable`` for the ring-level decision. For each seeded dataset
(labels stripped, as in the other evaluations) this reports, over mule accounts:

* ``legacy``: rings Louvain alone called suspicious, which is how the batch pipeline used to decide;
* ``shared_gate``: rings the shared rule accepts, which is what the pipeline alerts on now;
* ``live``: accounts in rings the scorer flagged while the payments were replayed one by one;
* ``agreement``: Jaccard overlap between ``shared_gate`` and ``live``.

Synthetic data only: agreement here is not proof of agreement on real traffic.

Usage (from the repository root):
    python scripts/evaluation/evaluate_engine_agreement.py --seeds 5 --out docs/buildx/engine_agreement.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Dict, Iterable, List, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from detection.ring_decision import (  # noqa: E402
    MERCHANT_TYPE,
    multi_scale_evidence,
    ring_is_flaggable,
    with_ring_evidence,
)
from evaluate_detectors import build_case  # noqa: E402
from evaluate_payments import TEST_SEEDS  # noqa: E402
from services.realtime_scorer import RealtimeScorer  # noqa: E402

from models.community_detection.louvain_detector import LouvainClusterDetector  # noqa: E402


def _union(sets: Iterable[Set[str]]) -> Set[str]:
    return set().union(*sets) if sets else set()


def _recall_precision(predicted: Set[str], mules: Set[str]) -> Dict[str, float]:
    hit = len(predicted & mules)
    return {"recall": round(hit / max(len(mules), 1), 4), "precision": round(hit / max(len(predicted), 1), 4)}


def run_seed(seed: int, scenario: str) -> Dict:
    accounts, txns, labels = build_case(seed, scenario)
    txns = sorted(txns, key=lambda t: str(t["timestamp"]))
    mules = {acc for acc, is_mule in labels.items() if is_mule}
    merchants = frozenset(a["account_id"] for a in accounts if a.get("account_type") == MERCHANT_TYPE)

    communities = LouvainClusterDetector().detect_clusters(txns, accounts)
    evidence = multi_scale_evidence(txns)
    legacy = _union([set(c.accounts) for c in communities if c.is_mule_cluster])
    shared = _union(
        [set(c.accounts) for c in communities if ring_is_flaggable(c, with_ring_evidence(evidence, c, txns), merchants)]
    )

    scorer = RealtimeScorer(accounts, [])
    live: Set[str] = set()
    for txn in txns:
        score = scorer.score_payment(txn)
        if score.decision == "FLAG":
            live |= set(score.ring_members)

    return {
        "seed": seed,
        "legacy": _recall_precision(legacy, mules),
        "shared_gate": _recall_precision(shared, mules),
        "live": _recall_precision(live, mules),
        "agreement": round(len(shared & live) / max(len(shared | live), 1), 4),
    }


def summarise(rows: List[Dict]) -> Dict:
    def mean(key: str, metric: str) -> float:
        return round(statistics.mean(r[key][metric] for r in rows), 4)

    return {
        **{key: {m: mean(key, m) for m in ("recall", "precision")} for key in ("legacy", "shared_gate", "live")},
        "agreement_mean": round(statistics.mean(r["agreement"] for r in rows), 4),
        "agreement_min": min(r["agreement"] for r in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seeds", type=int, default=5, help="how many test seeds to run")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    seeds = list(TEST_SEEDS)[: args.seeds]
    result = {"seeds": seeds, "scenarios": {}}
    for scenario in ("standard", "hardened"):
        rows = [run_seed(seed, scenario) for seed in seeds]
        result["scenarios"][scenario] = {"summary": summarise(rows), "per_seed": rows}
        print(scenario, json.dumps(result["scenarios"][scenario]["summary"]))
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(result, fh, indent=2)


if __name__ == "__main__":
    main()
