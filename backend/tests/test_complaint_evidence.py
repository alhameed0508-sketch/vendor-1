"""Evidence chain and classification for fraud complaints."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from complaints.evidence import GENESIS, append, classify, mule_summary, verify_chain


def _chain(*items):
    chain = []
    for n, (kind, data) in enumerate(items):
        chain = append(
            chain,
            at=f"2027-02-01T10:{n:02d}:00+05:30",
            source=_SOURCE[kind],
            kind=kind,
            summary=f"{kind} happened",
            data=data,
            submitted_by="test",
            received_at=f"2027-02-01T11:{n:02d}:00+05:30",
        )
    return chain


_SOURCE = {
    "transaction": "BANK_CORE",
    "sms_alert": "SMS_GATEWAY",
    "login": "AUTH_LOG",
    "sim_swap": "TELECOM",
    "credential_disclosed": "CUSTOMER",
    "bank_breach": "BANK_SECURITY",
    "delivery_confirmed": "COURIER",
    "device_history": "MERCHANT",
    "return_inspection": "MERCHANT",
    "mule_match": "MULECATCH",
}
SENT = ("sms_alert", {"delivered": True})
KNOWN_LOGIN = ("login", {"new_device": False, "otp_verified": True})
DELIVERED = ("delivery_confirmed", {"address_matches": True, "otp_verified": True})
REPEAT_DEVICE = ("device_history", {"prior_orders": 14, "same_device": True})


class TestChain:
    def test_items_get_sequential_ids_and_link_to_the_previous_hash(self):
        chain = _chain(SENT, KNOWN_LOGIN)
        assert [i["id"] for i in chain] == ["E1", "E2"]
        assert chain[0]["prev_hash"] == GENESIS
        assert chain[1]["prev_hash"] == chain[0]["hash"]
        assert verify_chain(chain) == {"intact": True, "broken_at": None}

    def test_append_does_not_mutate_the_chain(self):
        chain = _chain(SENT)
        append(
            chain,
            at="2027-02-01T12:00:00+05:30",
            source="AUTH_LOG",
            kind="login",
            summary="x",
            data={},
            submitted_by="t",
            received_at="2027-02-01T12:00:00+05:30",
        )
        assert len(chain) == 1

    def test_editing_any_item_breaks_the_chain_at_that_item(self):
        chain = _chain(SENT, KNOWN_LOGIN, DELIVERED)
        tampered = [chain[0], {**chain[1], "summary": "edited later"}, chain[2]]
        assert verify_chain(tampered) == {"intact": False, "broken_at": "E2"}

    @pytest.mark.parametrize(("field", "value"), [("kind", "made_up"), ("source", "NOWHERE")])
    def test_unknown_kind_or_source_is_rejected(self, field, value):
        args = {
            "at": "2027-02-01T12:00:00+05:30",
            "source": "AUTH_LOG",
            "kind": "login",
            "summary": "x",
            "data": {},
            "submitted_by": "t",
            "received_at": "2027-02-01T12:00:00+05:30",
            field: value,
        }
        with pytest.raises(ValueError):
            append([], **args)


class TestClassify:
    def test_undelivered_alert_is_bank_negligence_even_if_otp_was_shared(self):
        result = classify(_chain(("sms_alert", {"delivered": False}), ("credential_disclosed", {})))
        assert result["category"] == "BANK_NEGLIGENCE"
        assert result["reasons"][0]["evidence"] == ["E1"]

    def test_shared_otp_with_full_proof_is_customer_negligence(self):
        result = classify(_chain(SENT, KNOWN_LOGIN, ("credential_disclosed", {})))
        assert result["category"] == "CUSTOMER_NEGLIGENCE"
        assert result["proof_complete"] is True
        assert all(item["met"] and item["evidence"] for item in result["checklist"])

    def test_missing_alert_record_leaves_the_proof_incomplete(self):
        result = classify(_chain(KNOWN_LOGIN, ("credential_disclosed", {})))
        assert result["category"] == "CUSTOMER_NEGLIGENCE"
        assert result["proof_complete"] is False
        assert [c["met"] for c in result["checklist"]] == [True, False, True]

    def test_delivery_and_device_history_show_the_customer_made_the_payment(self):
        result = classify(_chain(SENT, KNOWN_LOGIN, DELIVERED, REPEAT_DEVICE))
        assert result["category"] == "NOT_FRAUD"
        assert result["proof_complete"] is True

    def test_sim_swap_is_a_third_party_breach(self):
        assert classify(_chain(SENT, ("sim_swap", {})))["category"] == "THIRD_PARTY_BREACH"
        assert classify(_chain(("login", {"new_device": True})))["category"] == "THIRD_PARTY_BREACH"

    def test_money_to_a_mule_account_overrides_delivery_evidence(self):
        result = classify(_chain(SENT, KNOWN_LOGIN, DELIVERED, REPEAT_DEVICE, ("mule_match", {"alert_id": "ALT_1"})))
        assert result["category"] != "NOT_FRAUD"
        assert "MULE_BENEFICIARY" in result["flags"]

    def test_swapped_return_is_flagged_as_return_abuse(self):
        result = classify(_chain(SENT, DELIVERED, ("return_inspection", {"item_matches": False})))
        assert "RETURN_ABUSE" in result["flags"]

    def test_no_decisive_evidence_is_undetermined(self):
        result = classify(_chain(SENT))
        assert result["category"] == "UNDETERMINED"
        assert result["checklist"] == []
        assert result["proof_complete"] is False


@pytest.mark.parametrize(("role", "text"), [("AGGREGATOR", "is an aggregator"), ("MULE", "is a mule")])
def test_mule_summary_reads_naturally(role, text):
    assert text in mule_summary("AC_1", {"role": role, "alert_id": "ALT_1"})
