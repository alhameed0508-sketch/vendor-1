"""RBI fraudulent-EBT rules (RBI/2026-27/167): deadlines, liability and compensation."""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from complaints.rules import IST, assess_liability, compensation, deadlines, format_inr

T0 = datetime(2027, 2, 1, 14, 0, tzinfo=IST)


def _deadlines(**overrides):
    args = {
        "occurred_at": T0,
        "reported_at": T0 + timedelta(hours=3),
        "cross_border": False,
        "channel": "UPI",
        "now": T0 + timedelta(days=10),
    }
    return deadlines(**{**args, **overrides})


class TestDeadlines:
    def test_domestic_complaint_must_be_resolved_within_45_days_of_the_report(self):
        d = _deadlines()
        assert d["resolve_by"] == T0 + timedelta(hours=3, days=45)
        assert d["days_left"] == 35
        assert d["overdue"] is False

    def test_cross_border_complaint_gets_60_days(self):
        assert _deadlines(cross_border=True)["resolve_by"] == T0 + timedelta(hours=3, days=60)

    def test_overdue_once_the_limit_passes(self):
        d = _deadlines(now=T0 + timedelta(days=46))
        assert d["overdue"] is True
        assert d["days_left"] == -1

    def test_credit_card_fraud_needs_a_shadow_credit_within_5_days(self):
        assert _deadlines(channel="CREDIT_CARD")["shadow_credit_by"] == T0 + timedelta(hours=3, days=5)
        assert _deadlines(channel="UPI")["shadow_credit_by"] is None

    @pytest.mark.parametrize(("days_late", "inside"), [(0, True), (5, True), (6, False)])
    def test_zero_liability_window_counts_calendar_days(self, days_late, inside):
        d = _deadlines(reported_at=T0 + timedelta(days=days_late))
        assert d["reported_after_days"] == days_late
        assert d["within_zero_liability_window"] is inside

    def test_rules_apply_only_to_transactions_from_2027(self):
        assert _deadlines()["rules_in_force"] is True
        old = datetime(2026, 12, 31, 23, 0, tzinfo=IST)
        assert _deadlines(occurred_at=old, reported_at=old)["rules_in_force"] is False


def _assess(category, *, window=True, proof=True, amount=40_000, after=0):
    return assess_liability(
        category=category,
        amount=amount,
        amount_after_report=after,
        within_zero_liability_window=window,
        proof_complete=proof,
    )


class TestLiability:
    def test_bank_negligence_means_zero_liability_whenever_reported(self):
        r = _assess("BANK_NEGLIGENCE", window=False)
        assert (r["customer_liability"], r["bank_liability"]) == (0, 40_000)

    def test_third_party_breach_reported_in_time_is_zero_liability(self):
        assert _assess("THIRD_PARTY_BREACH")["customer_liability"] == 0

    def test_late_third_party_report_falls_to_bank_policy_not_a_guess(self):
        r = _assess("THIRD_PARTY_BREACH", window=False)
        assert r["outcome"] == "BANK_POLICY"
        assert r["customer_liability"] is None

    def test_customer_negligence_customer_bears_loss_until_reported(self):
        r = _assess("CUSTOMER_NEGLIGENCE", amount=40_000, after=6_000)
        assert (r["customer_liability"], r["bank_liability"]) == (34_000, 6_000)

    def test_unproven_customer_liability_falls_on_the_bank(self):
        for category in ("CUSTOMER_NEGLIGENCE", "NOT_FRAUD"):
            r = _assess(category, proof=False)
            assert r["outcome"] == "UNPROVEN"
            assert r["customer_liability"] == 0

    def test_payment_the_customer_made_is_not_a_fraudulent_ebt(self):
        r = _assess("NOT_FRAUD")
        assert (r["outcome"], r["customer_liability"], r["bank_liability"]) == ("NOT_FRAUD", 40_000, 0)

    def test_undetermined_case_cannot_hold_the_customer_liable(self):
        assert _assess("UNDETERMINED")["customer_liability"] == 0


def _compensate(**overrides):
    args = {
        "category": "CUSTOMER_NEGLIGENCE",
        "loss": 40_000,
        "recovered": 15_000,
        "cross_border": False,
        "occurred_at": T0,
        "reported_after_days": 1,
        "ncrp_reported_after_days": 1,
        "is_individual": True,
        "previously_compensated": False,
        "form_received_at": None,
    }
    return compensation(**{**args, **overrides})


class TestCompensation:
    def test_matches_the_directions_worked_example(self):
        c = _compensate()
        assert c["eligible"] is True
        assert c["amount"] == 21_250
        assert c["split"] == {"rbi": 16_250, "customer_bank": 2_500, "beneficiary_bank": 2_500}

    def test_capped_at_25000_with_the_split_scaled(self):
        c = _compensate(loss=50_000, recovered=0)
        assert c["amount"] == 25_000
        assert c["split"] == {"rbi": 19_118, "customer_bank": 2_941, "beneficiary_bank": 2_941}

    def test_cross_border_has_no_beneficiary_bank_share(self):
        c = _compensate(loss=50_000, recovered=0, cross_border=True)
        assert c["split"] == {"rbi": 19_118, "customer_bank": 5_882}

    @pytest.mark.parametrize(
        "overrides",
        [
            {"category": "THIRD_PARTY_BREACH"},
            {"loss": 50_001},
            {"is_individual": False},
            {"reported_after_days": 6},
            {"ncrp_reported_after_days": None},
            {"previously_compensated": True},
            {"occurred_at": datetime(2028, 1, 1, 9, 0, tzinfo=IST)},
            {"occurred_at": datetime(2026, 12, 31, 9, 0, tzinfo=IST)},
        ],
    )
    def test_ineligible_cases_get_nothing_and_say_why(self, overrides):
        c = _compensate(**overrides)
        assert c["eligible"] is False
        assert c["amount"] == 0
        assert any(not check["met"] for check in c["checks"])

    def test_payout_due_5_days_after_the_completed_form(self):
        assert _compensate(form_received_at=T0)["pay_by"] == T0 + timedelta(days=5)
        assert _compensate()["pay_by"] is None


@pytest.mark.parametrize(
    ("amount", "text"),
    [(999, "₹999"), (64_999, "₹64,999"), (185_000, "₹1,85,000"), (12_345_678, "₹1,23,45,678"), (-2_500, "-₹2,500")],
)
def test_rupees_use_indian_digit_grouping(amount, text):
    assert format_inr(amount) == text
