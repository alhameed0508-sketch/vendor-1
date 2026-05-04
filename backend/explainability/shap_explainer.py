"""
MuleCatch SHAP Explainer
=========================
Computes actual SHAP values for GNN/heuristic model predictions using
shap.KernelExplainer (model-agnostic). Falls back gracefully to manual
marginal-contribution decomposition if shap is not installed.

References:
  - Lundberg & Lee (2017) "A Unified Approach to Interpreting Model Predictions"
  - shap.KernelExplainer works with any callable predict function
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Callable

import numpy as np


FEATURE_NAMES = [
    "account_age",
    "avg_monthly_txn",
    "kyc_verified",
    "high_risk_flag",
    "velocity_score",
    "amount_ceiling_score",
    "fan_out_score",
    "smurf_score",
]

FEATURE_DESCRIPTIONS = {
    "account_age": "Account age (normalized to 0-1 over 365 days)",
    "avg_monthly_txn": "Average monthly transaction count",
    "kyc_verified": "KYC verification status (1 = verified, 0 = pending)",
    "high_risk_flag": "Pre-existing high-risk flag on account",
    "velocity_score": "Transaction velocity burst score",
    "amount_ceiling_score": "Amount structuring below threshold score",
    "fan_out_score": "Fan-out ratio to unique recipients",
    "smurf_score": "Composite smurf-weighting score",
}

_shap_available: Optional[bool] = None


def _check_shap_available() -> bool:
    global _shap_available
    if _shap_available is None:
        try:
            import shap  # noqa: F401
            _shap_available = True
        except ImportError:
            _shap_available = False
    return _shap_available


@dataclass(frozen=True)
class SHAPFeatureValue:
    feature: str
    shap_value: float
    base_value: float
    feature_value: float
    description: str


@dataclass(frozen=True)
class SHAPResult:
    account_id: str
    base_value: float
    shap_values: List[SHAPFeatureValue]
    predicted_probability: float
    method: str  # "kernel_shap" | "manual_decomposition"

    def to_dict(self) -> Dict:
        return {
            "account_id": self.account_id,
            "base_value": self.base_value,
            "shap_values": [
                {
                    "feature": sv.feature,
                    "shap_value": sv.shap_value,
                    "base_value": sv.base_value,
                    "feature_value": sv.feature_value,
                    "description": sv.description,
                }
                for sv in self.shap_values
            ],
            "predicted_probability": self.predicted_probability,
            "method": self.method,
        }


def _build_node_features(alert: Dict) -> tuple:
    nodes = alert.get("nodes", [])
    if not nodes:
        return np.empty((0, len(FEATURE_NAMES))), []

    account_ids = []
    feature_rows = []

    for node in nodes:
        acc_id = node.get("account_id", "") if isinstance(node, dict) else node.account_id
        account_ids.append(acc_id)

        if isinstance(node, dict):
            age_days = node.get("account_age_days", 365)
            kyc = node.get("kyc_status", "UNKNOWN")
            smurf = node.get("smurf_score", 0.0)
        else:
            age_days = getattr(node, "account_age_days", 365)
            kyc = getattr(node, "kyc_status", "UNKNOWN")
            smurf = getattr(node, "smurf_score", 0.0)

        row = [
            min(age_days / 365.0, 1.0),
            0.5,
            1.0 if kyc == "VERIFIED" else 0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            float(smurf),
        ]
        feature_rows.append(row)

    return np.array(feature_rows, dtype=np.float64), account_ids


def _build_predict_fn(model_predict_fn: Optional[Callable]) -> Callable:
    if model_predict_fn is not None:
        return model_predict_fn

    weights = np.array([
        -0.15,  # account_age (older = less risky)
        0.05,   # avg_monthly_txn
        -0.10,  # kyc_verified (verified = less risky)
        0.10,   # high_risk_flag
        0.25,   # velocity_score
        0.20,   # amount_ceiling_score
        0.15,   # fan_out_score
        0.30,   # smurf_score
    ])

    def heuristic_predict(features: np.ndarray) -> np.ndarray:
        if features.ndim == 1:
            features = features.reshape(1, -1)
        raw = features @ weights
        return 1.0 / (1.0 + np.exp(-5.0 * (raw - 0.3)))

    return heuristic_predict


def compute_shap_values(
    alert: Dict,
    model_predict_fn: Optional[Callable] = None,
    max_samples: int = 50,
) -> List[SHAPResult]:
    features, account_ids = _build_node_features(alert)
    if features.shape[0] == 0:
        return []

    predict_fn = _build_predict_fn(model_predict_fn)

    if _check_shap_available():
        return _compute_with_shap(features, account_ids, predict_fn, max_samples)
    return _compute_manual_decomposition(features, account_ids, predict_fn)


def _compute_with_shap(
    features: np.ndarray,
    account_ids: List[str],
    predict_fn: Callable,
    max_samples: int,
) -> List[SHAPResult]:
    import shap

    if features.shape[0] > max_samples:
        indices = np.random.choice(features.shape[0], max_samples, replace=False)
        background = features[indices]
    else:
        background = features

    try:
        explainer = shap.KernelExplainer(predict_fn, background)
        shap_values = explainer.shap_values(features, nsamples=min(100, max_samples * 2))
    except Exception as exc:
        print(f"SHAP KernelExplainer failed ({exc}), using manual decomposition")
        return _compute_manual_decomposition(features, account_ids, predict_fn)

    base_value = float(explainer.expected_value)
    if isinstance(base_value, np.ndarray):
        base_value = float(base_value.flat[0])

    predictions = predict_fn(features)
    if predictions.ndim > 1:
        predictions = predictions[:, 0]

    results = []
    for i, acc_id in enumerate(account_ids):
        sv_row = shap_values[i] if shap_values.ndim > 1 else shap_values
        feature_values = []
        row_len = sv_row.shape[-1] if hasattr(sv_row, 'shape') else len(sv_row)
        for j, feat_name in enumerate(FEATURE_NAMES):
            if j >= row_len:
                break
            feature_values.append(SHAPFeatureValue(
                feature=feat_name,
                shap_value=round(float(sv_row[j]), 6),
                base_value=round(base_value, 6),
                feature_value=round(float(features[i, j]), 4),
                description=FEATURE_DESCRIPTIONS.get(feat_name, feat_name),
            ))

        feature_values = sorted(feature_values, key=lambda fv: -abs(fv.shap_value))

        results.append(SHAPResult(
            account_id=acc_id,
            base_value=round(base_value, 6),
            shap_values=feature_values,
            predicted_probability=round(float(predictions[i]), 4),
            method="kernel_shap",
        ))

    return sorted(results, key=lambda r: -r.predicted_probability)


def _compute_manual_decomposition(
    features: np.ndarray,
    account_ids: List[str],
    predict_fn: Callable,
) -> List[SHAPResult]:
    predictions = predict_fn(features)
    if predictions.ndim > 1:
        predictions = predictions[:, 0]

    feature_means = features.mean(axis=0)
    base_prediction = float(predict_fn(feature_means.reshape(1, -1)).flat[0])

    results = []
    for i, acc_id in enumerate(account_ids):
        feature_values = []
        for j, feat_name in enumerate(FEATURE_NAMES):
            if j >= features.shape[1]:
                break
            modified = features[i].copy()
            modified[j] = feature_means[j]
            pred_without = float(predict_fn(modified.reshape(1, -1)).flat[0])
            contribution = float(predictions[i]) - pred_without

            feature_values.append(SHAPFeatureValue(
                feature=feat_name,
                shap_value=round(contribution, 6),
                base_value=round(base_prediction, 6),
                feature_value=round(float(features[i, j]), 4),
                description=FEATURE_DESCRIPTIONS.get(feat_name, feat_name),
            ))

        feature_values = sorted(feature_values, key=lambda fv: -abs(fv.shap_value))

        results.append(SHAPResult(
            account_id=acc_id,
            base_value=round(base_prediction, 6),
            shap_values=feature_values,
            predicted_probability=round(float(predictions[i]), 4),
            method="manual_decomposition",
        ))

    return sorted(results, key=lambda r: -r.predicted_probability)


def format_for_waterfall_chart(shap_result: SHAPResult) -> Dict:
    waterfall_data = []
    running_total = shap_result.base_value

    waterfall_data.append({
        "name": "Base Rate",
        "value": round(shap_result.base_value, 4),
        "cumulative": round(running_total, 4),
        "fill": "#94a3b8",
        "type": "base",
    })

    for sv in shap_result.shap_values:
        running_total += sv.shap_value
        waterfall_data.append({
            "name": sv.feature.replace("_", " ").title(),
            "value": round(sv.shap_value, 4),
            "cumulative": round(running_total, 4),
            "feature_value": sv.feature_value,
            "fill": "#ef4444" if sv.shap_value > 0 else "#22c55e",
            "type": "positive" if sv.shap_value > 0 else "negative",
            "description": sv.description,
        })

    waterfall_data.append({
        "name": "Prediction",
        "value": round(shap_result.predicted_probability, 4),
        "cumulative": round(shap_result.predicted_probability, 4),
        "fill": "#f97316" if shap_result.predicted_probability > 0.5 else "#3b82f6",
        "type": "total",
    })

    return {
        "account_id": shap_result.account_id,
        "method": shap_result.method,
        "waterfall": waterfall_data,
    }
