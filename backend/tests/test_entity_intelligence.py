"""Entity links and cross-module correlation: scores stay per module and fuzzy matches are never merged."""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fraud_modules.intelligence.correlate import correlate
from fraud_modules.intelligence.entities import EntityRef, Link, link_accounts
from fraud_modules.rule_modules import Finding


def _acct(account_id, **extra):
    return {"account_id": account_id, **extra}


def _txn(i, src, dst, device=""):
    return {"txn_id": str(i), "from_account": src, "to_account": dst, "amount": 5.0, "device_id": device}


def _links(accounts, txns=()):
    return {(link.a.entity_id, link.b.entity_id): link for link in link_accounts(accounts, list(txns))}


def test_shared_cif_id_is_a_verified_link():
    links = _links([_acct("A", cif_id="C1"), _acct("B", cif_id="C1"), _acct("C", cif_id="C2")])
    assert links[("A", "B")].confidence == "VERIFIED"
    assert "CIF_ID" in links[("A", "B")].basis
    assert len(links) == 1


def test_shared_device_is_a_verified_link():
    links = _links([_acct("A"), _acct("B")], [_txn(1, "A", "X", "D1"), _txn(2, "B", "X", "D1")])
    assert links[("A", "B")].confidence == "VERIFIED"
    assert "device" in links[("A", "B")].basis


def test_similar_names_without_a_verified_identifier_are_only_possible():
    links = _links([_acct("A", holder_name="Rahul Sharma"), _acct("B", holder_name="Rahul Sharmaa")])
    assert links[("A", "B")].confidence == "POSSIBLE"


def test_a_verified_link_is_not_downgraded_by_a_name_match():
    accounts = [_acct("A", cif_id="C1", holder_name="Asha Rao"), _acct("B", cif_id="C1", holder_name="Asha Rao")]
    links = _links(accounts)
    assert len(links) == 1
    assert links[("A", "B")].confidence == "VERIFIED"


def test_different_names_and_no_shared_ids_make_no_link():
    assert _links([_acct("A", holder_name="Asha Rao"), _acct("B", holder_name="Vikram Singh")]) == {}


def test_a_name_match_never_merges_entities():
    accounts = [_acct("A", holder_name="Rahul Sharma"), _acct("B", holder_name="Rahul Sharmaa")]
    findings = [Finding("upi", "A", "R17", "R17: x"), Finding("upi", "B", "R17", "R17: x")]
    entities = correlate(findings)
    assert {e.entity.entity_id for e in entities} == {"A", "B"}
    assert accounts and all(len(e.modules) == 1 for e in entities)


def test_account_flagged_by_two_modules_is_one_entity_with_both_evidence_lists():
    findings = [
        Finding("mule", "A", "ALERT", "Cluster alert", score=0.91),
        Finding("upi", "A", "R18", "R18: Shared device"),
        Finding("upi", "A", "R17", "R17: Velocity"),
    ]
    (entity,) = correlate(findings)
    assert entity.entity == EntityRef("account", "A")
    by_module = {m.module_id: m for m in entity.modules}
    assert set(by_module) == {"mule", "upi"}
    assert by_module["mule"].score == pytest.approx(0.91)
    assert by_module["upi"].score is None
    assert by_module["upi"].evidence == ("R18: Shared device", "R17: Velocity")


def test_correlation_has_no_combined_score_field():
    names = {
        f.name for cls in (type(correlate([Finding("upi", "A", "R17", "x")])[0]),) for f in dataclasses.fields(cls)
    }
    assert names == {"entity", "modules"}


def test_entities_flagged_by_more_modules_come_first():
    findings = [
        Finding("upi", "B", "R17", "x"),
        Finding("upi", "A", "R17", "x"),
        Finding("mule", "A", "ALERT", "y", score=0.5),
    ]
    assert [e.entity.entity_id for e in correlate(findings)] == ["A", "B"]


def test_no_findings_gives_no_entities():
    assert correlate([]) == ()


def test_link_is_immutable():
    link = Link(EntityRef("account", "A"), EntityRef("account", "B"), "same CIF_ID", "VERIFIED")
    with pytest.raises(AttributeError):
        link.confidence = "POSSIBLE"
