"""
Measure how well each RuleEngine rule separates mule accounts from genuine ones.

A rule earns its place only if it fires clearly more often on mules than on genuine
accounts. Rules fire into reason codes shown to analysts, so a rule that fires on most
genuine accounts adds noise to every case. Synthetic data only: a rule that passes here
is not proven on real traffic.

Usage (from the repository root):
    python scripts/evaluation/evaluate_rules.py --seeds 20 --out docs/buildx/rule_discrimination.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from evaluate_detectors import build_case  # noqa: E402
from evaluate_payments import TEST_SEEDS  # noqa: E402

from backend.detection.pipeline import RuleEngine  # noqa: E402

MIN_LIFT = 3.0  # mule rate must be at least this many times the genuine rate
MIN_MULE_RATE = 0.10  # and the rule must reach at least this share of mules


def rule_rates(hits: Dict[str, List[str]], is_mule: Dict[str, bool], codes: List[str]) -> Dict[str, Dict[str, float]]:
    """Share of mule and of genuine accounts each rule fired on."""
    n_mule = sum(1 for m in is_mule.values() if m)
    n_genuine = len(is_mule) - n_mule
    rates = {}
    for code in codes:
        fired = {acc for acc, hs in hits.items() if any(h.startswith(f"{code}:") for h in hs)}
        rates[code] = {
            "mule": sum(1 for a in fired if is_mule.get(a)) / max(n_mule, 1),
            "genuine": sum(1 for a in fired if a in is_mule and not is_mule[a]) / max(n_genuine, 1),
        }
    return rates


def verdict(rate: Dict[str, float]) -> str:
    """'keep' only when the rule fires on enough mules and at least MIN_LIFT times as often as on genuine accounts.

    'untested' when it never fires on either side: the synthetic data cannot exercise it.
    """
    if rate["mule"] == 0 and rate["genuine"] == 0:
        return "untested"
    if rate["mule"] < MIN_MULE_RATE:
        return "drop"
    return "keep" if rate["mule"] >= MIN_LIFT * rate["genuine"] else "drop"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--scenario", default="standard", help="standard or hardened")
    parser.add_argument("--out", default="docs/buildx/rule_discrimination.json")
    args = parser.parse_args()

    engine = RuleEngine()
    codes = [code for code, _, _ in engine.RULES]
    descriptions = {code: desc for code, desc, _ in engine.RULES}
    seeds = list(TEST_SEEDS)[: args.seeds]
    totals = {c: {"mule": 0.0, "genuine": 0.0} for c in codes}
    for seed in seeds:
        accounts, txns, labels = build_case(seed, args.scenario)
        is_mule = {a: bool(v) for a, v in labels.items()}
        for code, rate in rule_rates(engine.evaluate(accounts, txns), is_mule, codes).items():
            for key in rate:
                totals[code][key] += rate[key] / len(seeds)

    report = {
        "seeds": seeds,
        "scenario": args.scenario,
        "rules": {
            c: {"description": descriptions[c], **{k: round(v, 3) for k, v in totals[c].items()}, "verdict": verdict(totals[c])}
            for c in codes
        },
    }
    for c, r in report["rules"].items():
        print(f"{c} {r['mule']:.2f} {r['genuine']:.2f} {r['verdict']:8} {r['description']}")
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main()
