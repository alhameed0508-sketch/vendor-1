"""
Per-payment evaluation of the real-time scorer (`services.realtime_scorer`).

Replays a held-out slice of each synthetic dataset through the scorer one
payment at a time and reports:

  * mule-payment recall: share of mule-to-mule payments that were flagged
  * genuine-payment flag rate: share of genuine-to-genuine payments flagged
  * genuine accounts exposed: genuine accounts inside any flagged ring
  * cases opened vs mule accounts covered
  * latency per payment (p50 / p95)

Controls (same as evaluate_detectors.py): ground-truth fields are removed
before scoring; the evidence gate is chosen on calibration seeds and applied
unchanged to separate test seeds; the "hardened" scenario equalises static
account attributes. Results are synthetic-data results only.

Usage (from the repository root):
    python scripts/evaluation/evaluate_payments.py --out docs/buildx/payment_eval_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from typing import Dict, List, Sequence

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import services.realtime_scorer as scorer_module  # noqa: E402
from evaluate_detectors import build_case  # noqa: E402
from evasion_playbooks import PLAYBOOKS  # noqa: E402
from services.realtime_scorer import RealtimeScorer  # noqa: E402

CALIBRATION_SEEDS = range(0, 3)
TEST_SEEDS = range(100, 120)
GATE_GRID = (0.25, 0.30, 0.35)
GENUINE_FLAG_BUDGET = 0.01  # genuine payments flagged, at most 1 %
LIVE_STRIDE = 15  # every 15th payment is replayed live; the rest is trusted history
SCENARIOS = ("standard", "hardened")


def _labels_with_roles(seed: int, scenario: str):
    """Return (accounts, txns, is_mule) with ground truth kept only in is_mule."""
    accounts, txns, labels = build_case(seed, scenario)
    return accounts, txns, {acc: bool(v) for acc, v in labels.items()}


def replay(seed: int, scenario: str, gate: float, stride: int = LIVE_STRIDE, playbook: str = None) -> Dict:
    accounts, txns, is_mule = _labels_with_roles(seed, scenario)
    if playbook:
        txns = PLAYBOOKS[playbook](txns, is_mule, random.Random(seed))
    return replay_case(accounts, txns, is_mule, gate, stride)


def replay_case(
    accounts: Sequence[Dict],
    txns: Sequence[Dict],
    is_mule: Dict[str, bool],
    gate: float,
    stride: int = LIVE_STRIDE,
    mule_payment_ids: frozenset = None,
) -> Dict:
    """Replay one labelled case. ``mule_payment_ids`` labels payments directly (when given, a mule
    payment is one in the set, and a genuine payment has two non-mule accounts and is not in it)."""
    txns = sorted(txns, key=lambda t: t["timestamp"])
    live = txns[::stride]
    history = [t for i, t in enumerate(txns) if i % stride]

    previous = scorer_module.ENDPOINT_EVIDENCE_MIN
    scorer_module.ENDPOINT_EVIDENCE_MIN = gate
    try:
        scorer = RealtimeScorer(accounts, history)
        mule_total = mule_flagged = genuine_total = genuine_flagged = 0
        latencies: List[float] = []
        cases: set = set()
        ring_accounts: set = set()
        caught: List[str] = []
        for txn in live:
            result = scorer.score_payment(txn, commit=True)
            latencies.append(result.latency_ms)
            both_mule = (
                txn["txn_id"] in mule_payment_ids
                if mule_payment_ids is not None
                else is_mule.get(txn["from_account"], False) and is_mule.get(txn["to_account"], False)
            )
            both_genuine = not is_mule.get(txn["from_account"], False) and not is_mule.get(txn["to_account"], False)
            flagged = result.decision == "FLAG"
            mule_total += both_mule
            genuine_total += both_genuine
            mule_flagged += flagged and both_mule
            if flagged and both_mule:
                caught.append(txn["txn_id"])
            genuine_flagged += flagged and both_genuine
            if flagged:
                cases.add(result.case_id)
                ring_accounts.update(result.ring_members)
    finally:
        scorer_module.ENDPOINT_EVIDENCE_MIN = previous

    mules = {a for a, m in is_mule.items() if m}
    return {
        "mule_payments": mule_total,
        "mule_flagged": mule_flagged,
        "genuine_payments": genuine_total,
        "genuine_flagged": genuine_flagged,
        "cases": len(cases),
        "mules_in_rings": len(ring_accounts & mules),
        "mules_total": len(mules),
        "genuine_exposed": len(ring_accounts - mules),
        "latencies_ms": latencies,
        "mule_flagged_ids": caught,
    }


def pool(rows: Sequence[Dict]) -> Dict:
    def ratio(num: str, den: str) -> float:
        total = sum(r[den] for r in rows)
        return round(sum(r[num] for r in rows) / total, 4) if total else 0.0

    lat = sorted(x for r in rows for x in r["latencies_ms"])
    return {
        "datasets": len(rows),
        "mule_payment_recall": ratio("mule_flagged", "mule_payments"),
        "genuine_payment_flag_rate": ratio("genuine_flagged", "genuine_payments"),
        "mule_accounts_covered": ratio("mules_in_rings", "mules_total"),
        "cases_opened_median": statistics.median(r["cases"] for r in rows),
        "genuine_accounts_exposed_median": statistics.median(r["genuine_exposed"] for r in rows),
        "latency_ms_p50": round(lat[len(lat) // 2], 1) if lat else None,
        "latency_ms_p95": round(lat[int(len(lat) * 0.95)], 1) if lat else None,
    }


def choose_gate(scenario: str, stride: int) -> Dict:
    """Highest mule recall with genuine flag rate within budget; ties go to the higher gate."""
    table = {gate: pool([replay(s, scenario, gate, stride) for s in CALIBRATION_SEEDS]) for gate in GATE_GRID}
    eligible = [g for g, m in table.items() if m["genuine_payment_flag_rate"] <= GENUINE_FLAG_BUDGET] or [
        max(GATE_GRID)
    ]
    best = max(eligible, key=lambda g: (table[g]["mule_payment_recall"], g))
    return {"chosen_gate": best, "calibration": {str(g): m for g, m in table.items()}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/buildx/payment_eval_results.json")
    parser.add_argument("--stride", type=int, default=LIVE_STRIDE)
    args = parser.parse_args()

    report: Dict = {"live_stride": args.stride, "genuine_flag_budget": GENUINE_FLAG_BUDGET, "scenarios": {}}
    for scenario in SCENARIOS:
        calibration = choose_gate(scenario, args.stride)
        gate = calibration["chosen_gate"]
        test = pool([replay(s, scenario, gate, args.stride) for s in TEST_SEEDS])
        report["scenarios"][scenario] = {**calibration, "test": test}
        print(f"[{scenario}] gate={gate} test={json.dumps(test)}", flush=True)

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
