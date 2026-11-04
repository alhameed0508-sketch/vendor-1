"""Time-separated evaluation on IBM AMLworld (HI-Small, LI-Small) for the problem statement:
"identify suspicious transactions in real time while minimising false alerts for genuine customers".

    python scripts/evaluation/evaluate_ibm_temporal.py --data-dir <folder with *-Small_Trans.csv>

Protocol: clean and validate the file (ibm_temporal/preprocess.py); split by time 60/20/20 on minute
boundaries; build point-in-time features (each payment sees only earlier minutes); fit on train;
choose hyperparameters and every threshold on validation; score the test split once.
The data is IBM's published synthetic dataset, not bank data. Writes docs/evaluation/ibm/ and
docs/IBM_AML_EVALUATION.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from ibm_temporal import features, metrics, models, preprocess, report  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "evaluation", "ibm")
OUT_MD = os.path.join(ROOT, "docs", "IBM_AML_EVALUATION.md")


def evaluate(data_dir: str, name: str) -> dict:
    started = time.perf_counter()
    df, quality = preprocess.load(os.path.join(data_dir, f"{name}_Trans.csv"))
    typ, typ_report = preprocess.typologies(df, os.path.join(data_dir, f"{name}_Patterns.txt"))
    train, val, test, tail, split = preprocess.chronological_split(df)
    t_pre = time.perf_counter() - started
    f = features.build(df)
    t_feat = time.perf_counter() - started - t_pre
    y = df.label.to_numpy().astype(np.int8)
    print(
        f"[{name}] rows={len(df):,} laundering={int(y.sum()):,} preprocess={t_pre:.0f}s features={t_feat:.0f}s",
        flush=True,
    )

    scores, info = {}, {}
    scores["static_rules"], info["static_rules"] = models.rule_scores(f, train)
    scores["logistic_regression"], info["logistic_regression"] = models.logistic(f, train, y)
    print(f"[{name}] logistic done", flush=True)
    scores["gradient_boosting"], info["gradient_boosting"], gbm = models.gradient_boosting(f, train, val, y)
    print(f"[{name}] gradient boosting done: {info['gradient_boosting']['chosen']}", flush=True)

    src = df.src.to_numpy()
    dst = df.dst.to_numpy()
    results = {}
    for model, s in scores.items():
        r = {
            "validation": metrics.threshold_free(y[val], s[val]),
            "test": metrics.threshold_free(y[test], s[test]),
            "operating_points": metrics.operating_points(y[val], s[val], y[test], s[test]),
            "curves_test": metrics.curve_points(y[test], s[test]),
        }
        _, av_label, av_score = metrics.account_level(src[val], dst[val], y[val], s[val])
        _, at_label, at_score = metrics.account_level(src[test], dst[test], y[test], s[test])
        acc_thr = metrics.threshold_best_f1(av_label, av_score)
        r["accounts"] = {
            "test": metrics.threshold_free(at_label, at_score),
            "best_f1_on_validation": metrics.at_threshold(at_label, at_score, acc_thr),
        }
        ops = r["operating_points"]
        r["typology_recall_test"] = {
            k: metrics.per_typology_recall(typ.to_numpy()[test], y[test], s[test], ops[k]["test"]["threshold"])
            for k in ops
        }
        if tail.any():  # wind-down days: almost only laundering, so reported apart from the test period
            r["tail_after_ordinary_traffic_ends"] = {
                k: metrics.at_threshold(y[tail], s[tail], ops[k]["test"]["threshold"]) for k in ops
            }
        results[model] = r
    lat = models.latency(gbm, f, np.flatnonzero(test))
    return {
        "dataset": name,
        "data_quality": quality,
        "typologies": typ_report,
        "split": split,
        "features": list(f.columns),
        "models": info,
        "results": results,
        "latency_gradient_boosting": lat,
        "runtime_seconds": round(time.perf_counter() - started, 1),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--datasets", nargs="+", default=["HI-Small", "LI-Small"])
    args = ap.parse_args(argv)
    os.makedirs(OUT_DIR, exist_ok=True)
    runs = [evaluate(args.data_dir, name) for name in args.datasets]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "IBM AMLworld (Altman et al., NeurIPS 2023): published synthetic data, not bank data",
        "runs": runs,
    }
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    for run in runs:
        report.plot_curves(run, OUT_DIR)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(report.markdown(payload))
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
