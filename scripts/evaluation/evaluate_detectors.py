"""
Leakage-controlled evaluation of MuleCatch detectors on synthetic data.

Compares four account-level detectors on the same held-out datasets:

  A0  account-age heuristic   (static-attribute shortcut, diagnostic only)
  A   rules baseline          (count of RuleEngine hits)
  B   graph + temporal        (max of smurf score and Louvain community suspicion)
  C   MuleCatch pipeline      (max alert risk_score containing the account)

Controls:
  * Ground-truth fields (role, high_risk, cluster_id, is_suspicious, pattern)
    are removed before any detector sees the data.
  * Operating thresholds are chosen on calibration seeds and applied unchanged
    to separate test seeds.
  * The "hardened" scenario resamples account age, KYC status and monthly
    activity from one shared distribution so static attributes cannot
    separate the classes; only behaviour and network structure remain.

Also reports investigator workload: review units (accounts or cases) needed
to reach 90 % mule recall, and legitimate accounts exposed along the way.

Usage (from the repository root):
    python scripts/evaluation/evaluate_detectors.py --out docs/buildx/evaluation_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from typing import Callable, Dict, List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from detection.pipeline import DetectionPipeline, RuleEngine  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

from data.synthetic.generator import build_adversarial_dataset  # noqa: E402
from models.community_detection.louvain_detector import LouvainClusterDetector  # noqa: E402
from models.temporal_weighting.smurf_weighting import score_transaction_batch  # noqa: E402

MULE_ROLES = {"MULE", "SOURCE", "AGGREGATOR"}
ACCOUNT_LABEL_FIELDS = {"role", "high_risk", "cluster_id"}
TXN_LABEL_FIELDS = {"is_suspicious", "pattern", "cluster_id"}

CALIBRATION_SEEDS = range(0, 5)
TEST_SEEDS = range(100, 120)
DATASET_PARAMS = {"num_clusters": 5, "num_legit_accounts": 150, "num_adversarial": 50}
FPR_BUDGET = 0.02  # false-alert budget for the low-FPR operating point

Scores = Dict[str, float]
Labels = Dict[str, int]


# ── Data ────────────────────────────────────────────────────────────────────


def build_case(seed: int, scenario: str) -> Tuple[List[Dict], List[Dict], Labels]:
    random.seed(seed)
    ds = build_adversarial_dataset(**DATASET_PARAMS)
    labels = {a["account_id"]: int(a.get("role") in MULE_ROLES) for a in ds["accounts"]}
    accounts = [{k: v for k, v in a.items() if k not in ACCOUNT_LABEL_FIELDS} for a in ds["accounts"]]
    txns = [{k: v for k, v in t.items() if k not in TXN_LABEL_FIELDS} for t in ds["transactions"]]
    if scenario == "hardened":
        accounts = _equalise_static_attributes(accounts, random.Random(seed + 10_000))
    return accounts, txns, labels


def _equalise_static_attributes(accounts: List[Dict], rng: random.Random) -> List[Dict]:
    return [
        {
            **a,
            "account_age_days": rng.randint(1, 3650),
            "kyc_status": "VERIFIED" if rng.random() < 0.8 else "PENDING",
            "avg_monthly_txn": rng.randint(5, 500),
        }
        for a in accounts
    ]


# ── Detectors (each returns a score per account; higher = more suspicious) ──


def score_age_heuristic(accounts, txns) -> Scores:
    return {a["account_id"]: 1.0 - min(a.get("account_age_days", 3650), 3650) / 3650 for a in accounts}


def score_rules(accounts, txns) -> Scores:
    hits = RuleEngine().evaluate(accounts, txns)
    return {a["account_id"]: float(len(hits.get(a["account_id"], []))) for a in accounts}


def score_graph_temporal(accounts, txns) -> Scores:
    smurf = score_transaction_batch(txns)
    communities = LouvainClusterDetector().detect_clusters(txns, accounts)
    community_score = {acc: c.suspicion_score for c in communities for acc in c.accounts}
    return {
        a["account_id"]: max(
            smurf[a["account_id"]].smurf_score if a["account_id"] in smurf else 0.0,
            community_score.get(a["account_id"], 0.0),
        )
        for a in accounts
    }


def score_pipeline(accounts, txns) -> Scores:
    scores = {a["account_id"]: 0.0 for a in accounts}
    for alert in DetectionPipeline().run(txns, accounts):
        for node in alert.nodes:
            if node.account_id in scores:
                scores[node.account_id] = max(scores[node.account_id], alert.risk_score)
    return scores


DETECTORS: Dict[str, Callable[[List[Dict], List[Dict]], Scores]] = {
    "A0_account_age_heuristic": score_age_heuristic,
    "A_rules_baseline": score_rules,
    "B_graph_temporal": score_graph_temporal,
    "C_mulecatch_pipeline": score_pipeline,
}


# ── Metrics ─────────────────────────────────────────────────────────────────


def confusion(scores: Scores, labels: Labels, threshold: float) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for acc, y in labels.items():
        pred = bool(scores.get(acc, 0.0) >= threshold)
        tp += int(pred and y == 1)
        fp += int(pred and y == 0)
        tn += int(not pred and y == 0)
        fn += int(not pred and y == 1)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def rates(c: Dict[str, int]) -> Dict[str, float]:
    precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    fpr = c["fp"] / (c["fp"] + c["tn"]) if c["fp"] + c["tn"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "fpr": fpr, "f1": f1}


def pooled(runs: List[Tuple[Scores, Labels]], threshold: float) -> Dict[str, float]:
    total = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for scores, labels in runs:
        for k, v in confusion(scores, labels, threshold).items():
            total[k] += v
    return {**total, **rates(total)}


def choose_thresholds(runs: List[Tuple[Scores, Labels]]) -> Dict[str, float]:
    candidates = sorted({float(s) for scores, _ in runs for s in scores.values()} | {float("inf")})
    best_f1 = max(candidates, key=lambda t: pooled(runs, t)["f1"])
    within_budget = [t for t in candidates if pooled(runs, t)["fpr"] <= FPR_BUDGET]
    low_fpr = min(within_budget, key=lambda t: (-pooled(runs, t)["recall"], t))
    return {"max_f1": best_f1, "fpr_budget": low_fpr}


def average_precision(runs: List[Tuple[Scores, Labels]]) -> float:
    y, s = [], []
    for scores, labels in runs:
        for acc, label in labels.items():
            y.append(label)
            s.append(scores.get(acc, 0.0))
    return float(average_precision_score(y, s))


# ── Investigator workload ───────────────────────────────────────────────────
# A review unit is what an analyst opens: one account for account-level
# detectors, one case (alert = community of accounts) for the pipeline.

RECALL_TARGET = 0.9


def units_to_target(units: List[Tuple[int, int]], total_mules: int) -> Dict:
    """units: ranked (mules, legit) per review unit. Returns effort to reach RECALL_TARGET."""
    found = legit = 0
    for opened, (m, lg) in enumerate(units, start=1):
        found += m
        legit += lg
        if total_mules and found / total_mules >= RECALL_TARGET:
            return {"reached": True, "units_opened": opened, "legit_accounts_exposed": legit}
    return {"reached": False, "units_opened": len(units), "legit_accounts_exposed": legit}


def account_units(scores: Scores, labels: Labels) -> List[Tuple[int, int]]:
    ranked = sorted(labels, key=lambda a: -scores.get(a, 0.0))
    return [(labels[a], 1 - labels[a]) for a in ranked if scores.get(a, 0.0) > 0]


def case_units(accounts, txns, labels: Labels) -> Dict[str, List[Tuple[int, int]]]:
    """Ranked case queues: as shipped (risk_score) and purity-weighted.

    Purity weighting multiplies the alert's risk by the mean smurf score of its
    members, so a community whose members carry little individual evidence
    drops down the queue. It uses no labels and no size threshold.
    """
    smurf = score_transaction_batch(txns)
    cases = []
    for alert in DetectionPipeline().run(txns, accounts):
        ids = {n.account_id for n in alert.nodes if n.account_id in labels}
        mules = sum(labels[i] for i in ids)
        member_evidence = statistics.mean(smurf[i].smurf_score if i in smurf else 0.0 for i in ids) if ids else 0.0
        cases.append((alert.risk_score, alert.risk_score * member_evidence, (mules, len(ids) - mules)))
    return {
        "as_shipped": [c[2] for c in sorted(cases, key=lambda c: -c[0])],
        "purity_weighted": [c[2] for c in sorted(cases, key=lambda c: -c[1])],
    }


def summarise_workload(results: List[Dict]) -> Dict:
    reached = [r for r in results if r["reached"]]
    return {
        "datasets_reaching_target": f"{len(reached)}/{len(results)}",
        "median_units_opened": statistics.median(r["units_opened"] for r in results),
        "median_legit_accounts_exposed": statistics.median(r["legit_accounts_exposed"] for r in results),
    }


def evaluate_workload(test: List[Tuple]) -> Dict:
    out = {"recall_target": RECALL_TARGET}
    for name in ("A_rules_baseline", "B_graph_temporal"):
        out[f"{name}_account_queue"] = summarise_workload(
            [units_to_target(account_units(DETECTORS[name](a, t), y), sum(y.values())) for a, t, y in test]
        )
    queues = [(case_units(a, t, y), sum(y.values())) for a, t, y in test]
    for variant in ("as_shipped", "purity_weighted"):
        out[f"C_mulecatch_case_queue_{variant}"] = summarise_workload(
            [units_to_target(q[variant], total) for q, total in queues]
        )
    return out


# ── Experiment ──────────────────────────────────────────────────────────────


def run_detector(name: str, cases: List[Tuple]) -> Tuple[List[Tuple[Scores, Labels]], List[float]]:
    runs, latencies = [], []
    for accounts, txns, labels in cases:
        start = time.perf_counter()
        scores = DETECTORS[name](accounts, txns)
        latencies.append(time.perf_counter() - start)
        runs.append((scores, labels))
    return runs, latencies


def evaluate_scenario(scenario: str) -> Dict:
    calibration = [build_case(s, scenario) for s in CALIBRATION_SEEDS]
    test = [build_case(s, scenario) for s in TEST_SEEDS]
    result = {"dataset": _describe(test), "detectors": {}}
    for name in DETECTORS:
        cal_runs, _ = run_detector(name, calibration)
        thresholds = choose_thresholds(cal_runs)
        test_runs, latencies = run_detector(name, test)
        n_txns = statistics.mean(len(c[1]) for c in test)
        result["detectors"][name] = {
            "thresholds_from_calibration": {k: (None if v == float("inf") else v) for k, v in thresholds.items()},
            "test_average_precision": round(average_precision(test_runs), 4),
            "test_at_max_f1_threshold": _round(pooled(test_runs, thresholds["max_f1"])),
            "test_at_fpr_budget_threshold": _round(pooled(test_runs, thresholds["fpr_budget"])),
            "median_latency_seconds": round(statistics.median(latencies), 4),
            "throughput_txns_per_second": round(n_txns / statistics.median(latencies), 1),
        }
        if name == "C_mulecatch_pipeline":
            result["detectors"][name]["test_as_shipped_alerting"] = _round(pooled(test_runs, 1e-9))
    result["investigator_workload"] = evaluate_workload(test)
    return result


def _describe(cases: List[Tuple]) -> Dict:
    accounts = [len(c[2]) for c in cases]
    mules = [sum(c[2].values()) for c in cases]
    return {
        "test_seeds": f"{min(TEST_SEEDS)}-{max(TEST_SEEDS)}",
        "calibration_seeds": f"{min(CALIBRATION_SEEDS)}-{max(CALIBRATION_SEEDS)}",
        "generator_params": DATASET_PARAMS,
        "mean_accounts_per_dataset": statistics.mean(accounts),
        "mean_mule_accounts_per_dataset": statistics.mean(mules),
        "mule_prevalence": round(sum(mules) / sum(accounts), 4),
        "mean_transactions_per_dataset": statistics.mean(len(c[1]) for c in cases),
    }


def _round(d: Dict) -> Dict:
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in d.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default=None, help="Write JSON results to this path")
    args = parser.parse_args()

    results = {
        "fpr_budget": FPR_BUDGET,
        "scenarios": {s: evaluate_scenario(s) for s in ("standard", "hardened")},
    }
    text = json.dumps(results, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    main()
