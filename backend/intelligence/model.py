"""Learned weights that turn the engines' outputs into one calibrated 0-100 score.

L2 logistic regression over ten features. Each feature's contribution is weight x value in log-odds, so
the explanation is exact rather than approximated. Weights are trained offline on a time-separated
window (scripts/evaluation/evaluate_unified.py) and stored as reviewed JSON with a SHA-256, never as a
pickle. Until a trained file exists, built-in prior weights are used and the version says so.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence

FEATURES = (
    "mule_network",
    "session_device",
    "beneficiary_intent",
    "behaviour",
    "familiarity",
    "corroboration",
    "new_payee",
    "new_device",
    "amount_log_ratio",
    "confidence",
)
FEATURE_LABELS = {
    "mule_network": "Mule network (core)",
    "session_device": "Session & device trust",
    "beneficiary_intent": "Payment intent & beneficiary",
    "behaviour": "Behaviour vs the customer's normal",
    "familiarity": "Familiarity (lowers risk)",
    "corroboration": "Engines agreeing",
    "new_payee": "New payee",
    "new_device": "New device",
    "amount_log_ratio": "Amount vs the customer's usual",
    "confidence": "Baseline confidence",
}
PRIOR = {
    "version": "prior-2026.11",
    "intercept": -4.0,
    "weights": {
        "mule_network": 4.0,
        "session_device": 3.5,
        "beneficiary_intent": 3.5,
        "behaviour": 2.0,
        "familiarity": -2.0,
        "corroboration": 1.2,
        "new_payee": 0.4,
        "new_device": 0.3,
        "amount_log_ratio": 0.15,
        "confidence": 0.0,
    },
    "trained_on": None,
}
DEFAULT_PATH = Path(__file__).resolve().parent / "model" / "risk_model.json"
CLIP = {"amount_log_ratio": (-3.0, 8.0), "corroboration": (0.0, 4.0)}


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def vectorise(features: Dict[str, float]) -> List[float]:
    out = []
    for name in FEATURES:
        v = float(features.get(name, 0.0))
        lo, hi = CLIP.get(name, (0.0, 1.0))
        out.append(min(max(v, lo), hi))
    return out


class RiskModel:
    def __init__(self, spec: Dict):
        weights = spec["weights"]
        missing = [f for f in FEATURES if f not in weights]
        if missing:
            raise ValueError(f"model weights missing {missing}")
        self.version = spec["version"]
        self.intercept = float(spec["intercept"])
        self.weights = {f: float(weights[f]) for f in FEATURES}
        self.spec = spec

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "RiskModel":
        path = path or DEFAULT_PATH
        if path.exists():
            raw = path.read_bytes()
            spec = json.loads(raw)
            spec.setdefault("sha256", hashlib.sha256(raw).hexdigest())
            return cls(spec)
        return cls(dict(PRIOR))

    def probability(self, features: Dict[str, float]) -> float:
        x = vectorise(features)
        z = self.intercept + sum(self.weights[f] * v for f, v in zip(FEATURES, x))
        return _sigmoid(z)

    def contributions(self, features: Dict[str, float]) -> Dict[str, float]:
        """Log-odds contribution of each feature (weight x clipped value)."""
        x = vectorise(features)
        return {f: round(self.weights[f] * v, 4) for f, v in zip(FEATURES, x) if self.weights[f] * v}

    def describe(self) -> Dict:
        return {
            "version": self.version,
            "intercept": self.intercept,
            "weights": self.weights,
            "trained_on": self.spec.get("trained_on"),
            "metrics": self.spec.get("metrics"),
            "sha256": self.spec.get("sha256"),
        }


def fit(rows: Sequence[Dict[str, float]], labels: Sequence[int], version: str, trained_on: str, c: float = 1.0) -> Dict:
    """Train L2 logistic regression on engine features. Returns a JSON-ready spec."""
    from sklearn.linear_model import LogisticRegression

    X = [vectorise(r) for r in rows]
    model = LogisticRegression(C=c, max_iter=2000)
    model.fit(X, list(labels))
    return {
        "version": version,
        "intercept": round(float(model.intercept_[0]), 5),
        "weights": {f: round(float(w), 5) for f, w in zip(FEATURES, model.coef_[0])},
        "trained_on": trained_on,
        "features": list(FEATURES),
    }


def save(spec: Dict, path: Optional[Path] = None) -> Path:
    path = path or DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(spec, indent=2, sort_keys=True)
    path.write_text(body, encoding="utf-8")
    return path
