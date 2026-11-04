"""The three scorers compared: bank-style static rules, logistic regression, gradient-boosted trees.

All are fitted on the training split only. Rule thresholds come from training-split percentiles (no
labels). Model hyperparameters are chosen on the validation split by PR-AUC.
"""

from __future__ import annotations

import time
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from ibm_temporal.features import CATEGORICAL

HEAVY_TAILED = (
    "s_out_count",
    "s_out_24h",
    "s_in_count",
    "s_in_24h",
    "s_mins_since_last_in",
    "s_mins_since_last_out",
    "s_age_mins",
    "s_distinct_payees",
    "r_in_count",
    "r_in_24h",
    "r_out_count",
    "r_out_24h",
    "r_distinct_payers",
    "r_age_mins",
    "r_mins_since_last_out",
    "pair_count",
    "pair_mins_since_last",
)
HGB_GRID = [
    {"max_leaf_nodes": 31, "class_weight": None},
    {"max_leaf_nodes": 127, "class_weight": None},
    {"max_leaf_nodes": 31, "class_weight": "balanced"},
    {"max_leaf_nodes": 127, "class_weight": "balanced"},
]


def rule_scores(f: pd.DataFrame, train: np.ndarray) -> Tuple[np.ndarray, Dict]:
    """Five static rules a bank might run; score = number of rules hit (0-5)."""
    t = f.loc[train]
    cut = {
        "high_amount_p99": float(np.percentile(t.log_amount_usd, 99)),
        "new_payee_amount_p90": float(np.percentile(t.log_amount_usd, 90)),
        "payer_velocity_24h_p99": float(np.percentile(t.s_out_24h, 99)),
        "payee_inflow_24h_p99": float(np.percentile(t.r_in_24h, 99)),
        "pass_through_amount_p75": float(np.percentile(t.log_amount_usd, 75)),
    }
    hits = (
        (f.log_amount_usd > cut["high_amount_p99"]).astype(int)
        + ((f.new_pair == 1) & (f.log_amount_usd > cut["new_payee_amount_p90"])).astype(int)
        + (f.s_out_24h > cut["payer_velocity_24h_p99"]).astype(int)
        + (f.r_in_24h > cut["payee_inflow_24h_p99"]).astype(int)
        + ((f.s_mins_since_last_in <= 60) & (f.log_amount_usd > cut["pass_through_amount_p75"])).astype(int)
    )
    return hits.to_numpy().astype(float), {"rules": list(cut), "thresholds_from_training_split": cut}


def _linear_matrix(f: pd.DataFrame) -> np.ndarray:
    x = f.drop(columns=list(CATEGORICAL)).copy()
    for c in HEAVY_TAILED:
        x[c] = np.log1p(np.clip(x[c].to_numpy(dtype=np.float64), 0, None))
    dummies = [pd.get_dummies(f[c].astype("int16"), prefix=c, dtype=np.float32) for c in CATEGORICAL]
    return pd.concat([x.astype(np.float32)] + dummies, axis=1).to_numpy(dtype=np.float32)


def logistic(f: pd.DataFrame, train: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, Dict]:
    x = _linear_matrix(f)
    scaler = StandardScaler().fit(x[train])
    xs = scaler.transform(x).astype(np.float32)
    started = time.perf_counter()
    model = LogisticRegression(C=1.0, max_iter=300).fit(xs[train], y[train])
    return model.predict_proba(xs)[:, 1], {"fit_seconds": round(time.perf_counter() - started, 1), "C": 1.0}


def gradient_boosting(f: pd.DataFrame, train: np.ndarray, val: np.ndarray, y: np.ndarray):
    """Fit the grid on train, keep the one with the best validation PR-AUC. Returns (scores, info, model)."""
    cat_mask = [c in CATEGORICAL for c in f.columns]
    x = f.to_numpy(dtype=np.float32)
    best, tried = None, []
    for params in HGB_GRID:
        started = time.perf_counter()
        model = HistGradientBoostingClassifier(
            learning_rate=0.1,
            max_iter=300,
            l2_regularization=1.0,
            categorical_features=cat_mask,
            early_stopping=False,
            random_state=0,
            **params,
        ).fit(x[train], y[train])
        s_val = model.predict_proba(x[val])[:, 1]
        ap = float(average_precision_score(y[val], s_val))
        tried.append(
            {**params, "validation_pr_auc": round(ap, 5), "fit_seconds": round(time.perf_counter() - started, 1)}
        )
        if best is None or ap > best[0]:
            best = (ap, params, model)
    _, params, model = best
    return model.predict_proba(x)[:, 1], {"chosen": params, "grid": tried}, model


def latency(model, f: pd.DataFrame, rows: np.ndarray, repeats: int = 300) -> Dict:
    """Model inference time for one payment (features already computed) and batch throughput."""
    x = f.to_numpy(dtype=np.float32)
    one = []
    for i in rows[:repeats]:
        started = time.perf_counter()
        model.predict_proba(x[i : i + 1])
        one.append((time.perf_counter() - started) * 1000)
    batch = x[rows[: min(len(rows), 100_000)]]
    started = time.perf_counter()
    model.predict_proba(batch)
    per = (time.perf_counter() - started) / len(batch)
    return {
        "single_payment_ms_p50": float(np.percentile(one, 50)),
        "single_payment_ms_p95": float(np.percentile(one, 95)),
        "batch_payments_per_second": float(1 / per),
    }
