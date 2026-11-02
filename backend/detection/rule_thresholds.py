"""Thresholds for the surviving rules (R01-R06, R12-R15, R17, R20), as data instead of literals.

Defaults are the values the rules used before they were externalised. A bank overrides them with
the RULE_THRESHOLDS setting, a JSON object naming only the values to change, so a model risk
committee can approve a config diff instead of a code change. Unknown names and out-of-range values
are rejected at startup rather than ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from typing import Any, Dict

RATIO_FIELDS = frozenset({"structured_ratio", "upi_digit_ratio"})


@dataclass(frozen=True)
class RuleThresholds:
    # R01 new account; R02 burst; R03 KYC pending with volume
    new_account_age_days: int = 7
    missing_age_days: int = 999  # age assumed when the record has none
    burst_txn_count: int = 20
    kyc_pending_min_txns: int = 5
    # R04 amounts structured just under the reporting ceiling
    structured_lower: float = 40000
    structured_upper: float = 50000
    structured_min_txns: int = 3
    structured_ratio: float = 0.7
    # R05 dormant account suddenly active
    dormant_min_age_days: int = 180
    dormant_max_monthly_txn: int = 3
    dormant_min_outgoing: int = 8
    # R06 same-day credit and debit
    same_day_overlap_days: int = 2
    # R12 identical amounts; R13 multi-city
    identical_amount_recipients: int = 3
    multi_city_count: int = 3
    # R14 split transactions
    split_amount_upper: float = 10000
    split_min_count: int = 5
    split_total: float = 100000
    # R15 high-risk UPI handle
    upi_digit_ratio: float = 0.6
    upi_min_length: int = 10
    # R17 velocity acceleration
    velocity_baseline_monthly: int = 10
    velocity_factor: float = 2
    # R20 72-hour anomaly
    early_age_days: int = 3
    early_min_txns: int = 5
    early_min_amount: float = 100000

    def __post_init__(self) -> None:
        if self.structured_lower >= self.structured_upper:
            raise ValueError("structured_lower must be below structured_upper")

    @classmethod
    def from_json(cls, text: str) -> "RuleThresholds":
        """Defaults plus the overrides in ``text`` (empty means no overrides)."""
        if not text or not text.strip():
            return cls()
        try:
            overrides = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"RULE_THRESHOLDS is not valid JSON: {exc}") from exc
        if not isinstance(overrides, dict):
            raise ValueError("RULE_THRESHOLDS must be a JSON object")
        return cls.from_overrides(overrides)

    @classmethod
    def from_overrides(cls, overrides: Dict[str, Any]) -> "RuleThresholds":
        known = {f.name: f for f in fields(cls)}
        unknown = sorted(set(overrides) - set(known))
        if unknown:
            raise ValueError(f"unknown rule threshold(s): {', '.join(unknown)}")
        for name, value in overrides.items():
            _check(name, value, known[name].type)
        return replace(cls(), **overrides)


def _check(name: str, value: Any, kind: str) -> None:
    ok = isinstance(value, int) if kind == "int" else isinstance(value, (int, float))
    if isinstance(value, bool) or not ok:
        raise ValueError(f"{name} must be a {'whole number' if kind == 'int' else 'number'}")
    if value < 0 or (name in RATIO_FIELDS and value > 1):
        raise ValueError(f"{name} must be {'between 0 and 1' if name in RATIO_FIELDS else 'zero or more'}")
