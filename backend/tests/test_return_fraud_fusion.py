"""Fusion: context-aware weights, a corroboration firewall and four decision tiers."""

import pytest
from return_fraud.fusion import BLOCK_MIN_SIGNALS, fuse
from return_fraud.signals import SIGNAL_NAMES, Signal


def _sig(name, score, confidence=1.0, available=True):
    return Signal(name=name, score=score, confidence=confidence, available=available, reasons=(f"{name} reason",))


def _all(score, **overrides):
    return [_sig(n, overrides.get(n, score)) for n in SIGNAL_NAMES]


def test_quiet_claim_is_approved():
    result = fuse(_all(5), context={})
    assert result["tier"] == "APPROVE"
    assert result["score"] < 35


def test_middling_score_asks_for_verification():
    result = fuse(_all(50), context={})
    assert result["tier"] == "VERIFY"


def test_one_loud_signal_never_blocks():
    result = fuse(_all(0, receipt=100), context={})
    assert result["tier"] == "VERIFY"  # a person looks, but nothing is blocked
    assert "No single signal" in result["firewall"]


def test_one_loud_signal_cannot_even_challenge():
    result = fuse(_all(40, receipt=100), context={"high_value": True})
    assert result["tier"] == "VERIFY"


def test_two_corroborating_signals_can_challenge():
    result = fuse(_all(70, device=70, graph=70, exif=70, receipt=70, vlm=70, behavioral=70), context={})
    assert result["tier"] in {"CHALLENGE", "BLOCK"}


def test_block_needs_three_primary_signals_above_sixty():
    three = fuse(_all(0, receipt=95, exif=95, device=95), context={})
    assert three["corroborating"] == BLOCK_MIN_SIGNALS
    only_two = fuse(_all(30, receipt=99, exif=99), context={})
    assert only_two["tier"] != "BLOCK"
    assert only_two["corroborating"] == 2


def test_all_signals_high_blocks():
    result = fuse(_all(95), context={})
    assert result["tier"] == "BLOCK"
    assert result["score"] >= 81
    assert result["corroborating"] == len(SIGNAL_NAMES)


def test_firewall_reports_the_tier_it_capped():
    two_loud = fuse([_sig("receipt", 100), _sig("exif", 100), _sig("vlm", 50)], context={})
    assert two_loud["capped_from"] == "BLOCK"
    assert two_loud["tier"] == "CHALLENGE"
    assert two_loud["corroborating"] == 2


def test_unavailable_signal_is_left_out_not_counted_as_clean():
    signals = [_sig(n, 90) for n in SIGNAL_NAMES[:3]] + [_sig(n, 0, available=False) for n in SIGNAL_NAMES[3:]]
    result = fuse(signals, context={})
    assert result["score"] >= 81
    assert result["missing"] == list(SIGNAL_NAMES[3:])


def test_carrier_route_fault_lowers_the_score():
    base = fuse(_all(70), context={})["score"]
    with_fault = fuse(_all(70), context={"carrier_fault": True})["score"]
    assert with_fault < base
    assert fuse(_all(70), context={"carrier_fault": True})["adjustments"][0]["label"].startswith("Carrier")


def test_context_changes_weights():
    signals = _all(10, receipt=90)
    plain = fuse(signals, context={})["raw_score"]
    high_value = fuse(signals, context={"high_value": True})["raw_score"]
    assert high_value > plain


def test_low_confidence_signal_counts_for_less():
    confident = fuse([_sig("receipt", 90, 1.0)] + _all(10)[1:], context={})["score"]
    unsure = fuse([_sig("receipt", 90, 0.3)] + _all(10)[1:], context={})["score"]
    assert unsure < confident


def test_needs_at_least_one_available_signal():
    with pytest.raises(ValueError):
        fuse([_sig(n, 0, available=False) for n in SIGNAL_NAMES], context={})


def test_shown_score_agrees_with_the_tier():
    for result in (fuse(_all(0, receipt=100), context={}), fuse(_all(50), context={})):
        low, high = {"VERIFY": (35, 64.9), "CHALLENGE": (65, 80.9)}[result["tier"]]
        assert low <= result["score"] <= high


def test_contributions_add_up_to_the_score_before_adjustments():
    result = fuse(_all(10, receipt=90, exif=80, device=70), context={})
    assert sum(result["contributions"].values()) == pytest.approx(result["raw_score"], abs=0.3)
    assert result["contributions"]["receipt"] > result["contributions"]["exif"] > result["contributions"]["device"]


def test_contributions_plus_adjustments_reconcile_with_the_raw_score():
    result = fuse(_all(70), context={"carrier_fault": True})
    parts = sum(result["contributions"].values()) + sum(a["points"] for a in result["adjustments"])
    assert parts == pytest.approx(result["raw_score"], abs=0.3)


def test_a_quiet_claim_has_zero_contributions():
    assert set(fuse(_all(0), context={})["contributions"].values()) == {0.0}
