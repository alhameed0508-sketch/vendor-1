"""
Re-run the per-payment evaluation after mule operators adapt (see evasion_playbooks.py).

The evidence gate is fixed at the value chosen by evaluate_payments.py; nothing is
re-tuned per playbook. Reports the same pooled metrics for the baseline and for
each playbook. Synthetic data only.

Usage (from the repository root):
    python scripts/evaluation/evaluate_evasion.py --gate 0.30 --seeds 5 --out docs/buildx/evasion_results.json
"""

from __future__ import annotations

import argparse
import json

from evaluate_payments import LIVE_STRIDE, SCENARIOS, TEST_SEEDS, pool, replay
from evasion_playbooks import PLAYBOOKS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=float, default=0.30)
    parser.add_argument("--seeds", type=int, default=5, help="number of test seeds per cell")
    parser.add_argument("--stride", type=int, default=LIVE_STRIDE)
    parser.add_argument("--out", default="docs/buildx/evasion_results.json")
    args = parser.parse_args()

    seeds = list(TEST_SEEDS)[: args.seeds]
    report = {"gate": args.gate, "seeds": seeds, "live_stride": args.stride, "scenarios": {}}
    for scenario in SCENARIOS:
        cells = {}
        for name in (None, *PLAYBOOKS):
            cells[name or "baseline"] = pool([replay(s, scenario, args.gate, args.stride, name) for s in seeds])
            print(f"[{scenario}/{name or 'baseline'}] {json.dumps(cells[name or 'baseline'])}", flush=True)
        report["scenarios"][scenario] = cells

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
