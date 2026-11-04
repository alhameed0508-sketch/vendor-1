"""The seeded scenarios must land in the tier each one is meant to demonstrate."""

import pytest
from return_fraud.assess import assess_claim
from return_fraud.seed import SCENARIOS, seed_claims

EXPECTED = {
    "legit": "APPROVE",
    "receipt_manipulation": "VERIFY",
    "exif_mismatch": "CHALLENGE",
    "ring": "BLOCK",
    "wardrobing": "VERIFY",
    "friendly_fraud": "VERIFY",
    "inr_carrier_fault": "APPROVE",
}


@pytest.fixture(scope="module")
def claims():
    return seed_claims()


def _result(claims, scenario):
    claim = next(c for c in claims if c["scenario"] == scenario and c.get("headline", True))
    return assess_claim(claim, claims)


def test_every_scenario_is_seeded():
    assert set(SCENARIOS) == set(EXPECTED)


@pytest.mark.parametrize("scenario,tier", EXPECTED.items())
def test_scenario_lands_in_its_tier(claims, scenario, tier):
    assert _result(claims, scenario)["fusion"]["tier"] == tier


def test_receipt_manipulation_shows_the_firewall_at_work(claims):
    r = _result(claims, "receipt_manipulation")
    assert r["fusion"]["corroborating"] == 1
    assert r["fusion"]["tier"] != "BLOCK"


def test_ring_is_blocked_on_three_or_more_signals(claims):
    r = _result(claims, "ring")
    assert r["fusion"]["corroborating"] >= 3
    assert r["fusion"]["score"] >= 81


def test_carrier_fault_is_why_the_big_claim_is_approved(claims):
    r = _result(claims, "inr_carrier_fault")
    assert r["fusion"]["adjustments"]
    assert r["claim"]["amount"] >= 100000


def test_assessment_never_leaks_raw_bytes(claims):
    import json

    json.dumps(_result(claims, "ring"))  # raises if bytes are present
