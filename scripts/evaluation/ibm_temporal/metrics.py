"""Metrics for the problem statement: catch suspicious payments while keeping false alerts low.

Thresholds are always chosen on the validation split and applied unchanged to the test split.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve

FALSE_ALERT_BUDGETS = (0.001, 0.005)  # share of genuine payments a bank tolerates interrupting


def threshold_best_f1(y: np.ndarray, s: np.ndarray) -> float:
    p, r, t = precision_recall_curve(y, s)
    f1 = np.where(p + r > 0, 2 * p * r / np.maximum(p + r, 1e-12), 0)[:-1]
    return float(t[int(np.argmax(f1))]) if len(t) else float("inf")


def threshold_for_fpr(y: np.ndarray, s: np.ndarray, budget: float) -> float:
    """Lowest threshold whose false-positive rate on genuine payments stays within the budget."""
    genuine = np.sort(s[y == 0])
    if not len(genuine):
        return float("inf")
    k = int(np.floor(budget * len(genuine)))  # at most k genuine scores may be >= threshold
    if k == 0:
        return float(np.nextafter(genuine[-1], np.inf))
    cand = genuine[len(genuine) - k]
    # scores tied at the candidate would push us over budget: step just above it
    if (genuine >= cand).sum() > k:
        cand = np.nextafter(cand, np.inf)
    return float(cand)


def at_threshold(y: np.ndarray, s: np.ndarray, thr: float) -> Dict:
    pred = s >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(thr),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "alerts_per_10k_payments": 1e4 * (tp + fp) / len(y),
        "false_alerts_per_10k_genuine": 1e4 * fp / max(fp + tn, 1),
    }


def threshold_free(y: np.ndarray, s: np.ndarray) -> Dict:
    return {
        "roc_auc": float(roc_auc_score(y, s)),
        "pr_auc": float(average_precision_score(y, s)),
        "positives": int(y.sum()),
        "n": int(len(y)),
        "prevalence": float(y.mean()),
    }


def bootstrap_ci(y: np.ndarray, s: np.ndarray, thr: float, n_boot: int = 200, seed: int = 0) -> Dict:
    """95% intervals for precision, recall and F1 at a fixed threshold (resampling test payments)."""
    rng = np.random.default_rng(seed)
    pred = s >= thr
    out = {"precision": [], "recall": [], "f1": []}
    n = len(y)
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        yy, pp = y[i], pred[i]
        tp = (pp & (yy == 1)).sum()
        fp = (pp & (yy == 0)).sum()
        fn = (~pp & (yy == 1)).sum()
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        out["precision"].append(p)
        out["recall"].append(r)
        out["f1"].append(2 * p * r / (p + r) if p + r else 0.0)
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in out.items()}


def operating_points(y_val, s_val, y_test, s_test) -> Dict:
    """Thresholds picked on validation (best F1, and each false-alert budget), scored on test."""
    points = {"best_f1_on_validation": threshold_best_f1(y_val, s_val)}
    for b in FALSE_ALERT_BUDGETS:
        points[f"false_alerts_at_most_{b * 100:g}pct"] = threshold_for_fpr(y_val, s_val, b)
    out = {}
    for name, thr in points.items():
        out[name] = {"validation": at_threshold(y_val, s_val, thr), "test": at_threshold(y_test, s_test, thr)}
    best = points["best_f1_on_validation"]
    out["best_f1_on_validation"]["test_95ci"] = bootstrap_ci(y_test, s_test, best)
    return out


def account_level(src: np.ndarray, dst: np.ndarray, y: np.ndarray, s: np.ndarray):
    """Per-account score (max over its payments, as payer or payee) and label (in any laundering payment)."""
    accounts = np.concatenate([src, dst])
    score = np.concatenate([s, s])
    label = np.concatenate([y, y])
    codes, uniq = np.unique(accounts, return_inverse=True)
    acc_score = np.full(len(codes), -np.inf)
    np.maximum.at(acc_score, uniq, score)
    acc_label = np.zeros(len(codes), dtype=np.int8)
    np.maximum.at(acc_label, uniq, label)
    return codes, acc_label, acc_score


def per_typology_recall(typ: np.ndarray, y: np.ndarray, s: np.ndarray, thr: float) -> Dict:
    out = {}
    for t in sorted(set(typ[(y == 1) & (typ != "")])):
        m = (y == 1) & (typ == t)
        out[t] = {"laundering_payments": int(m.sum()), "recall": float((s[m] >= thr).mean())}
    unmatched = (y == 1) & (typ == "")
    if unmatched.any():
        out["(not in patterns file)"] = {
            "laundering_payments": int(unmatched.sum()),
            "recall": float((s[unmatched] >= thr).mean()),
        }
    return out


def curve_points(y: np.ndarray, s: np.ndarray, max_points: int = 400) -> Dict[str, Sequence[float]]:
    """Curves thinned on the axes that matter, not by index (most raw points crowd one end).

    ROC: true-positive rate at log-spaced false-positive rates (the step curve, read at each grid point).
    PR: precision at evenly spaced recall levels (the best precision reachable at that recall or more).
    """
    fpr, tpr, _ = roc_curve(y, s)
    grid_fpr = np.unique(np.r_[np.logspace(-6, 0, max_points), fpr[fpr > 0][:1]])
    grid_tpr = tpr[np.searchsorted(fpr, grid_fpr, side="right") - 1]
    p, r, _ = precision_recall_curve(y, s)  # recall decreasing
    order = np.argsort(r, kind="stable")
    r_sorted, p_sorted = r[order], p[order]
    best_from_here = np.maximum.accumulate(p_sorted[::-1])[::-1]  # max precision at recall >= r
    grid_r = np.linspace(0, 1, max_points)
    idx = np.minimum(np.searchsorted(r_sorted, grid_r, side="left"), len(r_sorted) - 1)
    return {
        "fpr": grid_fpr.tolist(),
        "tpr": grid_tpr.tolist(),
        "recall": grid_r.tolist(),
        "precision": best_from_here[idx].tolist(),
    }
