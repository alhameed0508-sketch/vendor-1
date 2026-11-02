"""Rule thresholds are config, not code: defaults match the old literals, overrides are validated."""

import dataclasses
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.detection.pipeline import DetectionPipeline, RuleEngine  # noqa: E402
from backend.detection.rule_thresholds import RuleThresholds  # noqa: E402

YOUNG = {"account_id": "A1", "account_age_days": 20}


def test_defaults_are_the_values_the_rules_used_before():
    th = RuleThresholds()
    assert (th.new_account_age_days, th.burst_txn_count, th.kyc_pending_min_txns) == (7, 20, 5)
    assert (th.structured_lower, th.structured_upper, th.structured_min_txns, th.structured_ratio) == (
        40000,
        50000,
        3,
        0.7,
    )
    assert (th.dormant_min_age_days, th.dormant_max_monthly_txn, th.dormant_min_outgoing) == (180, 3, 8)
    assert (th.split_amount_upper, th.split_min_count, th.split_total) == (10000, 5, 100000)
    assert (th.early_age_days, th.early_min_txns, th.early_min_amount) == (3, 5, 100000)


def test_empty_overrides_give_defaults():
    assert RuleThresholds.from_json("") == RuleThresholds()
    assert RuleThresholds.from_json("{}") == RuleThresholds()


def test_overrides_replace_only_the_named_values():
    th = RuleThresholds.from_json(json.dumps({"new_account_age_days": 30}))
    assert th.new_account_age_days == 30
    assert th.burst_txn_count == 20


@pytest.mark.parametrize(
    "text",
    [
        '{"no_such_threshold": 1}',  # a typo must not be silently ignored
        '{"new_account_age_days": "soon"}',
        '{"new_account_age_days": -1}',
        '{"structured_ratio": 1.5}',
        "[1, 2]",
        "not json",
    ],
)
def test_bad_overrides_are_rejected(text):
    with pytest.raises(ValueError):
        RuleThresholds.from_json(text)


def test_structured_band_must_be_ordered():
    with pytest.raises(ValueError):
        RuleThresholds.from_json('{"structured_lower": 60000}')


def test_thresholds_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        RuleThresholds().burst_txn_count = 1


def test_engine_uses_the_thresholds_it_is_given():
    default_hits = RuleEngine().evaluate([YOUNG], [])
    widened = RuleEngine(RuleThresholds(new_account_age_days=30)).evaluate([YOUNG], [])
    assert default_hits == {}
    assert "R01" in widened["A1"][0]


def test_pipeline_passes_thresholds_to_its_engine():
    th = RuleThresholds(burst_txn_count=3)
    assert DetectionPipeline(rule_thresholds=th).rule_engine.thresholds is th
