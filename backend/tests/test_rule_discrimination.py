"""Per-rule firing rates split by ground truth; a rule that fires as often on genuine accounts is noise."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "evaluation"))

from evaluate_rules import rule_rates, verdict  # noqa: E402

IS_MULE = {"M1": True, "M2": True, "G1": False, "G2": False, "G3": False, "G4": False}


def test_rule_rates_split_by_label():
    hits = {"M1": ["R01: x"], "M2": ["R01: x", "R02: y"], "G1": ["R02: y"]}
    rates = rule_rates(hits, IS_MULE, ["R01", "R02", "R03"])
    assert rates["R01"] == {"mule": 1.0, "genuine": 0.0}
    assert rates["R02"] == {"mule": 0.5, "genuine": 0.25}
    assert rates["R03"] == {"mule": 0.0, "genuine": 0.0}


def test_verdict_flags_rules_that_do_not_separate():
    assert verdict({"mule": 0.08, "genuine": 0.91}) == "drop"  # fires more on genuine
    assert verdict({"mule": 0.50, "genuine": 0.45}) == "drop"  # no real lift
    assert verdict({"mule": 0.04, "genuine": 0.00}) == "drop"  # too rare to matter
    assert verdict({"mule": 0.00, "genuine": 0.00}) == "untested"  # data cannot exercise it
    assert verdict({"mule": 0.60, "genuine": 0.05}) == "keep"


def test_rule_set_has_no_rule_measured_to_fire_more_on_genuine_accounts():
    """R07-R11, R16, R19 fired on 40-90% of genuine accounts and 0-8% of mules (docs/buildx/rule_discrimination.json)."""
    from backend.detection.pipeline import RuleEngine

    codes = {code for code, _, _ in RuleEngine.RULES}
    assert codes.isdisjoint({"R07", "R08", "R09", "R10", "R11", "R16", "R19"})
    assert {"R01", "R18"} <= codes
