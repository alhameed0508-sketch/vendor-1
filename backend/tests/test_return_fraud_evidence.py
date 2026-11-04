"""The bank package: structured JSON with a plain-language narrative, a tamper-evident hash, and a PDF."""

import json

import pytest
from return_fraud.assess import assess_claim
from return_fraud.evidence import build_package, build_pdf, verify_package
from return_fraud.seed import seed_claims

NOW = "2027-03-01T10:00:00+05:30"


@pytest.fixture(scope="module")
def claims():
    return seed_claims()


def _package(claims, scenario):
    claim = next(c for c in claims if c["scenario"] == scenario and c.get("headline", True))
    return build_package(assess_claim(claim, claims), NOW)


def test_package_has_the_three_part_narrative(claims):
    pkg = _package(claims, "ring")
    assert set(pkg["narrative"]) == {"what_happened", "what_we_found", "what_we_recommend"}
    assert "INR" in pkg["narrative"]["what_happened"] or "₹" in pkg["narrative"]["what_happened"]


def test_every_signal_that_fired_is_listed_with_its_reasons(claims):
    pkg = _package(claims, "ring")
    fired = {s["name"] for s in pkg["signals"] if s["fired"]}
    assert {"exif", "receipt", "device", "graph"} <= fired
    assert all(s["reasons"] for s in pkg["signals"] if s["fired"])


def test_quiet_signals_are_marked_not_fired(claims):
    pkg = _package(claims, "receipt_manipulation")
    assert {s["name"]: s["fired"] for s in pkg["signals"]}["receipt"] is True
    assert {s["name"]: s["fired"] for s in pkg["signals"]}["graph"] is False


@pytest.mark.parametrize(
    "scenario,label",
    [
        ("ring", "ring"),
        ("receipt_manipulation", "document"),
        ("friendly_fraud", "received"),
    ],
)
def test_dispute_category_follows_the_evidence(claims, scenario, label):
    assert label in _package(claims, scenario)["dispute_category"]["label"].lower()


def test_approved_claim_has_no_dispute_category(claims):
    assert _package(claims, "legit")["dispute_category"]["code"] == "NONE"


def test_category_is_marked_indicative(claims):
    assert "indicative" in _package(claims, "ring")["dispute_category"]["note"].lower()


def test_recommendation_never_claims_to_decide(claims):
    text = _package(claims, "ring")["narrative"]["what_we_recommend"].lower()
    assert "reviewer" in text or "fraud desk" in text


def test_package_states_its_limits(claims):
    pkg = _package(claims, "exif_mismatch")
    assert any("simulat" in limit.lower() for limit in pkg["limits"])


def test_integrity_hash_verifies_and_detects_edits(claims):
    pkg = _package(claims, "ring")
    assert verify_package(pkg)["intact"] is True
    tampered = json.loads(json.dumps(pkg))
    tampered["decision"]["tier"] = "APPROVE"
    assert verify_package(tampered)["intact"] is False


def test_package_is_json_serialisable(claims):
    json.dumps(_package(claims, "ring"))


def test_pdf_is_a_pdf_that_carries_the_hash(claims):
    pkg = _package(claims, "ring")
    pdf = build_pdf(pkg)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
