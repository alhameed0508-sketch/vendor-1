"""
Robustness and scaling probe for the MuleCatch detection pipeline.

1. Robustness: feeds deliberately malformed transaction batches straight into
   DetectionPipeline.run() and records whether each is handled or raises.
   (The CSV upload adapter validates files before this point; this probe
   tests what happens when another ingestion path skips validation.)
2. Scaling: measures wall-clock latency of one pipeline run as transaction
   volume grows.

Usage (from the repository root):
    python scripts/evaluation/robustness_and_scale.py --out docs/buildx/robustness_scale_results.json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from typing import Callable, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from detection.pipeline import DetectionPipeline  # noqa: E402

from data.synthetic.generator import build_adversarial_dataset  # noqa: E402

SCALE_POINTS = [(5, 150, 50), (10, 400, 100), (20, 1000, 200)]
# A fourth point (40 clusters, 2,500 legit, 400 adversarial) was stopped after
# more than 8 minutes on the audit machine: rule evaluation is O(accounts x transactions).


def _base_case():
    random.seed(7)
    ds = build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=20)
    return ds["accounts"], ds["transactions"]


def _mutate_first(txns: List[Dict], fn: Callable[[Dict], None]) -> List[Dict]:
    out = copy.deepcopy(txns)
    fn(out[0])
    return out


MALFORMED_CASES: Dict[str, Callable[[List[Dict], List[Dict]], tuple]] = {
    "empty_batch": lambda a, t: (a, []),
    "no_accounts": lambda a, t: ([], t),
    "amount_non_numeric": lambda a, t: (a, _mutate_first(t, lambda x: x.update(amount="abc"))),
    "amount_negative": lambda a, t: (a, _mutate_first(t, lambda x: x.update(amount=-500.0))),
    "amount_missing": lambda a, t: (a, _mutate_first(t, lambda x: x.pop("amount"))),
    "timestamp_missing": lambda a, t: (a, _mutate_first(t, lambda x: x.pop("timestamp"))),
    "timestamp_unparseable": lambda a, t: (a, _mutate_first(t, lambda x: x.update(timestamp="yesterday"))),
    "to_account_missing": lambda a, t: (a, _mutate_first(t, lambda x: x.pop("to_account"))),
    "self_transfer": lambda a, t: (a, _mutate_first(t, lambda x: x.update(to_account=x["from_account"]))),
    "unknown_counterparty": lambda a, t: (a, _mutate_first(t, lambda x: x.update(to_account="ACC_NOT_IN_MASTER"))),
    "duplicate_txn_ids": lambda a, t: (a, t + copy.deepcopy(t[:50])),
}


def probe_robustness() -> Dict[str, str]:
    accounts, txns = _base_case()
    results = {}
    for name, build in MALFORMED_CASES.items():
        acc, tx = build(copy.deepcopy(accounts), txns)
        try:
            alerts = DetectionPipeline().run(tx, acc)
            results[name] = f"handled ({len(alerts)} alerts)"
        except Exception as exc:  # recording the failure is the point of the probe
            results[name] = f"RAISED {type(exc).__name__}: {str(exc)[:80]}"
    return results


def probe_scale() -> List[Dict]:
    rows = []
    for clusters, legit, adversarial in SCALE_POINTS:
        random.seed(11)
        ds = build_adversarial_dataset(num_clusters=clusters, num_legit_accounts=legit, num_adversarial=adversarial)
        start = time.perf_counter()
        DetectionPipeline().run(ds["transactions"], ds["accounts"])
        elapsed = time.perf_counter() - start
        n = len(ds["transactions"])
        rows.append(
            {
                "accounts": len(ds["accounts"]),
                "transactions": n,
                "seconds": round(elapsed, 2),
                "txns_per_second": round(n / elapsed, 1),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default=None, help="Write JSON results to this path")
    args = parser.parse_args()
    results = {"robustness": probe_robustness(), "scaling": probe_scale()}
    text = json.dumps(results, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    main()
