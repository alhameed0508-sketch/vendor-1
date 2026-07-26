"""
Lightweight GNN Alternative
============================
XGBoost/LightGBM classifier on graph-extracted features as a fallback
when torch_geometric is unavailable. Falls back to heuristic scoring
if neither ML library is installed.

13 features: account_age, kyc_numeric, smurf_score, velocity, fan_out,
fan_in, rhythm, consolidation, in_degree, out_degree, betweenness,
pagerank, baseline_deviation.
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "lightweight_model.pkl")

# -- KYC status numeric mapping -----------------------------------------------
# Maps KYC verification status to a numeric risk indicator (0.0 = safest)
KYC_STATUS_SCORES = {
    "VERIFIED": 0.0,
    "COMPLETE": 0.1,
    "PARTIAL": 0.5,
    "PENDING": 0.8,
    "UNKNOWN": 0.6,
}
# Default KYC score when status is unrecognized
KYC_DEFAULT_SCORE = 0.6

# -- Feature normalization divisors -------------------------------------------
# Normalize account age to a 0-1 range (365 days = 1.0)
NORM_ACCOUNT_AGE_DAYS = 365.0
# Normalize transaction velocity (30 txns/period = 1.0)
NORM_VELOCITY_TXNS = 30.0
# Normalize fan-out / fan-in unique counterparties (10 = 1.0)
NORM_FAN_COUNTERPARTIES = 10.0
# Cap rhythm ratio before normalizing (2.0 = max ratio)
NORM_RHYTHM_CAP = 2.0
# Normalize in/out degree (20 = 1.0)
NORM_DEGREE = 20.0

# -- ML training parameters ---------------------------------------------------
# Learning rate for LightGBM and XGBoost gradient boosting
LEARNING_RATE = 0.1

# -- Heuristic fallback feature weights (must sum to ~1.0) --------------------
HEURISTIC_WEIGHTS = (
    0.08,  # account_age (inverted: young = risky)
    0.08,  # kyc_numeric (high = incomplete)
    0.20,  # smurf_score
    0.10,  # velocity
    0.08,  # fan_out
    0.06,  # fan_in
    0.05,  # rhythm
    0.05,  # consolidation
    0.05,  # in_degree
    0.05,  # out_degree
    0.07,  # betweenness
    0.05,  # pagerank
    0.08,  # baseline_deviation
)

FEATURE_NAMES = (
    "account_age", "kyc_numeric", "smurf_score", "velocity",
    "fan_out", "fan_in", "rhythm", "consolidation",
    "in_degree", "out_degree", "betweenness", "pagerank",
    "baseline_deviation",
)


@dataclass(frozen=True)
class LightweightPrediction:
    account_id: str
    mule_probability: float
    feature_importances: Tuple[Tuple[str, float], ...]


def _kyc_to_numeric(kyc_status: str) -> float:
    return KYC_STATUS_SCORES.get(kyc_status, KYC_DEFAULT_SCORE)


def extract_features(
    accounts: List[Dict],
    transactions: List[Dict],
    smurf_scores: Dict = None,
    centrality: Dict = None,
    baselines: Dict = None,
) -> Tuple[List[str], List[List[float]]]:
    """Build feature matrix from raw data.

    Returns (account_ids, feature_matrix) where feature_matrix is a list of
    13-element feature vectors.
    """
    smurf_scores = smurf_scores or {}
    centrality = centrality or {}
    baselines = baselines or {}

    # Pre-compute transaction stats
    outgoing_count: Dict[str, int] = {}
    incoming_count: Dict[str, int] = {}
    unique_recipients: Dict[str, set] = {}
    unique_senders: Dict[str, set] = {}
    incoming_total: Dict[str, float] = {}
    outgoing_total: Dict[str, float] = {}

    for t in transactions:
        src = t["from_account"]
        dst = t["to_account"]
        amt = float(t["amount"])

        outgoing_count[src] = outgoing_count.get(src, 0) + 1
        incoming_count[dst] = incoming_count.get(dst, 0) + 1
        unique_recipients.setdefault(src, set()).add(dst)
        unique_senders.setdefault(dst, set()).add(src)
        outgoing_total[src] = outgoing_total.get(src, 0.0) + amt
        incoming_total[dst] = incoming_total.get(dst, 0.0) + amt

    account_ids = []
    feature_matrix = []

    for acc in accounts:
        acc_id = acc["account_id"]
        account_ids.append(acc_id)

        age = min(acc.get("account_age_days", 30) / NORM_ACCOUNT_AGE_DAYS, 1.0)
        kyc = _kyc_to_numeric(acc.get("kyc_status", "UNKNOWN"))

        ss = smurf_scores.get(acc_id)
        smurf = ss.smurf_score if ss and hasattr(ss, "smurf_score") else 0.0

        velocity = min(outgoing_count.get(acc_id, 0) / NORM_VELOCITY_TXNS, 1.0)
        fan_out = min(len(unique_recipients.get(acc_id, set())) / NORM_FAN_COUNTERPARTIES, 1.0)
        fan_in = min(len(unique_senders.get(acc_id, set())) / NORM_FAN_COUNTERPARTIES, 1.0)

        out_amt = outgoing_total.get(acc_id, 0.0)
        in_amt = incoming_total.get(acc_id, 0.0)
        total_flow = out_amt + in_amt
        rhythm = min(out_amt / max(in_amt, 1.0), NORM_RHYTHM_CAP) / NORM_RHYTHM_CAP if in_amt > 0 else 0.5
        consolidation = in_amt / max(total_flow, 1.0)

        in_deg = min(incoming_count.get(acc_id, 0) / NORM_DEGREE, 1.0)
        out_deg = min(outgoing_count.get(acc_id, 0) / NORM_DEGREE, 1.0)

        cs = centrality.get(acc_id, {})
        betweenness = cs.get("betweenness", 0.0)
        pagerank = cs.get("pagerank", 0.0)

        bl = baselines.get(acc_id)
        baseline_dev = bl.composite_score if bl and hasattr(bl, "composite_score") else 0.0

        feature_matrix.append([
            age, kyc, smurf, velocity, fan_out, fan_in, rhythm,
            consolidation, in_deg, out_deg, betweenness, pagerank,
            baseline_dev,
        ])

    return account_ids, feature_matrix


class LightweightScorer:
    """Lightweight ML scorer using LightGBM/XGBoost with heuristic fallback."""

    def __init__(self, model_path: str = MODEL_PATH):
        self._model = None
        self._model_type = "heuristic"
        self._model_path = model_path
        self._try_load_model()

    def _try_load_model(self):
        """Attempt to load pre-trained model from disk."""
        if os.path.exists(self._model_path):
            try:
                with open(self._model_path, "rb") as f:
                    saved = pickle.load(f)
                self._model = saved["model"]
                self._model_type = saved.get("type", "unknown")
                logger.info("Lightweight scorer loaded: %s", self._model_type)
                return
            except Exception as exc:
                logger.warning("Failed to load lightweight model: %s", exc)

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def train(
        self,
        feature_matrix: List[List[float]],
        labels: List[int],
    ) -> Dict:
        """Train on labeled data. Tries LightGBM, then XGBoost, then skips."""
        if len(feature_matrix) < 10:
            logger.warning("Not enough data to train lightweight model (%d samples)", len(feature_matrix))
            return {"trained": False, "reason": "insufficient_data"}

        model = None
        model_type = None

        # Try LightGBM
        try:
            import lightgbm as lgb
            dataset = lgb.Dataset(feature_matrix, label=labels)
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "num_leaves": 31,
                "learning_rate": LEARNING_RATE,
                "verbose": -1,
            }
            model = lgb.train(params, dataset, num_boost_round=100)
            model_type = "lightgbm"
        except ImportError:
            pass

        # Try XGBoost
        if model is None:
            try:
                import xgboost as xgb
                dtrain = xgb.DMatrix(feature_matrix, label=labels)
                params = {
                    "objective": "binary:logistic",
                    "max_depth": 6,
                    "eta": LEARNING_RATE,
                    "eval_metric": "logloss",
                    "verbosity": 0,
                }
                model = xgb.train(params, dtrain, num_boost_round=100)
                model_type = "xgboost"
            except ImportError:
                pass

        if model is None:
            logger.info("Neither LightGBM nor XGBoost available; using heuristic fallback")
            return {"trained": False, "reason": "no_ml_library"}

        self._model = model
        self._model_type = model_type

        # Save model
        try:
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            with open(self._model_path, "wb") as f:
                pickle.dump({"model": model, "type": model_type}, f)
            logger.info("Lightweight model saved: %s", self._model_path)
        except Exception as exc:
            logger.warning("Failed to save lightweight model: %s", exc)

        return {"trained": True, "model_type": model_type, "samples": len(feature_matrix)}

    def predict(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict = None,
        centrality: Dict = None,
        baselines: Dict = None,
    ) -> List[LightweightPrediction]:
        """Predict mule probability for each account."""
        account_ids, features = extract_features(
            accounts, transactions, smurf_scores, centrality, baselines,
        )

        if not account_ids:
            return []

        if self._model is not None:
            probabilities = self._ml_predict(features)
        else:
            probabilities = [self._heuristic_predict(f) for f in features]

        results = []
        for acc_id, prob, feat in zip(account_ids, probabilities, features):
            importances = tuple(
                (name, round(abs(val), 4))
                for name, val in zip(FEATURE_NAMES, feat)
            )
            results.append(LightweightPrediction(
                account_id=acc_id,
                mule_probability=round(prob, 4),
                feature_importances=importances,
            ))

        return results

    def _ml_predict(self, features: List[List[float]]) -> List[float]:
        """Predict using the trained ML model."""
        try:
            if self._model_type == "lightgbm":
                return list(self._model.predict(features))
            elif self._model_type == "xgboost":
                import xgboost as xgb
                dmatrix = xgb.DMatrix(features)
                return list(self._model.predict(dmatrix))
        except Exception as exc:
            logger.warning("ML prediction failed, falling back to heuristic: %s", exc)
        return [self._heuristic_predict(f) for f in features]

    @staticmethod
    def _heuristic_predict(features: List[float]) -> float:
        """Rule-based fallback when no ML library is installed.

        Weighted combination of the 13 features with domain-knowledge weights.
        """
        # For account_age, invert (younger = riskier)
        adjusted = list(features)
        adjusted[0] = 1.0 - adjusted[0]  # invert age

        score = sum(w * v for w, v in zip(HEURISTIC_WEIGHTS, adjusted))
        return min(max(score, 0.0), 1.0)
