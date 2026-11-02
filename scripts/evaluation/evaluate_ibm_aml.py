"""
Evaluate the real-time scorer on IBM AMLworld (HI-Small), an independent dataset.

Nothing here is tuned: the evidence gate is the one chosen on our own synthetic data
(evaluate_payments.py), applied unchanged. Each case holds a few laundering attempts, each mule's
other payments (capped) and some ordinary accounts' payments (capped), replayed one payment at a
time like evaluate_payments.py. Reports pooled metrics and recall per laundering typology.

Download the data first (see docs/buildx/05-evaluation.md 7.8), then from the repository root:
    python scripts/evaluation/evaluate_ibm_aml.py --out docs/buildx/ibm_aml_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))
from evaluate_payments import ROOT, pool, replay_case  # noqa: E402
from services.realtime_scorer import _material_window, _multi_scale_evidence  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from data.adapters.ibm_aml_adapter import TXN_ID_PREFIX, IbmAml  # noqa: E402

DEFAULT_DIR = os.path.join(ROOT, "data", "external", "ibm-aml")
DEFAULT_GATE = 0.30
CASE_STRIDE = 5  # cases are small (a few thousand payments), so replay a larger share live


def _typology_of(aml: IbmAml) -> Dict[str, str]:
    return {f"{TXN_ID_PREFIX}{i}": a.typology for a in aml.attempts for i in a.rows}


def _typology_recall(rows: List[Dict], typology: Dict[str, str], live_ids: List[set]) -> Dict[str, Dict]:
    seen: Dict[str, int] = defaultdict(int)
    hit: Dict[str, int] = defaultdict(int)
    for row, live in zip(rows, live_ids):
        for txn_id in live:
            if txn_id in typology:
                seen[typology[txn_id]] += 1
        for txn_id in row["mule_flagged_ids"]:
            hit[typology[txn_id]] += 1
    return {t: {"mule_payments": seen[t], "recall": round(hit[t] / seen[t], 4)} for t in sorted(seen)}


def _evidence_labels(txns: List[Dict], is_mule: Dict[str, bool]):
    """Per-account smurf evidence (the scorer's own, multi-scale) against the mule label."""
    evidence = _multi_scale_evidence(_material_window(txns))
    return [(s.smurf_score, is_mule.get(a, False)) for a, s in evidence.items()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=DEFAULT_DIR)
    parser.add_argument("--gate", type=float, default=DEFAULT_GATE)
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--attempts", type=int, default=4, help="laundering attempts per case")
    parser.add_argument("--controls", type=int, default=60, help="ordinary accounts per case")
    parser.add_argument("--neighbor-cap", type=int, default=30, help="max other payments kept per account")
    parser.add_argument("--stride", type=int, default=CASE_STRIDE)
    parser.add_argument("--out", default="docs/buildx/ibm_aml_results.json")
    args = parser.parse_args()

    aml = IbmAml.load(os.path.join(args.dir, "HI-Small_Trans.csv"), os.path.join(args.dir, "HI-Small_Patterns.txt"))
    typology = _typology_of(aml)
    rows, live_ids, sizes, pairs = [], [], [], []
    for seed in range(args.cases):
        accounts, txns, is_mule = aml.build_case(random.Random(seed), args.attempts, args.controls, args.neighbor_cap)
        txns = sorted(txns, key=lambda t: t["timestamp"])
        live_ids.append({t["txn_id"] for t in txns[:: args.stride]} & aml.laundering_ids)
        rows.append(replay_case(accounts, txns, is_mule, args.gate, args.stride, frozenset(aml.laundering_ids)))
        sizes.append(len(txns))
        pairs.extend(_evidence_labels(txns, is_mule))
        print(f"[case {seed}] payments={len(txns)} {json.dumps({k: v for k, v in rows[-1].items() if k not in ('latencies_ms', 'mule_flagged_ids')})}", flush=True)

    report = {
        "dataset": "IBM AMLworld HI-Small (third-party mirror, unmodified)",
        "gate": args.gate,
        "cases": args.cases,
        "payments_per_case_median": sorted(sizes)[len(sizes) // 2],
        "pooled": pool(rows),
        "account_evidence_auc": round(roc_auc_score([int(y) for _, y in pairs], [x for x, _ in pairs]), 4),
        "by_typology": _typology_recall(rows, typology, live_ids),
    }
    print(json.dumps(report, indent=2))
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
