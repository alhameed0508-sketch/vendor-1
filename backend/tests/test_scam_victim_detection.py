"""Tests for scam victim detection (sender-side) and dual risk engine."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from models.scam.victim_detector import (
    ScamVictimDetector,
    ScamVictimResult,
    SCAM_KEYWORDS,
)
from models.scam.dual_risk_engine import DualRiskEngine, DualRiskResult


# ── Helpers ─────────────────────────────────────────────────────────────

def _txn(
    amount=10_000,
    is_new_beneficiary=False,
    narration="",
    account=None,
):
    """Build a minimal transaction dict."""
    result = {
        "amount": amount,
        "is_new_beneficiary": is_new_beneficiary,
        "narration": narration,
    }
    if account is not None:
        result["account"] = account
    return result


def _session(
    on_phone_call=False,
    backspace_count=0,
    amount_pasted=False,
    app_switch_count=0,
    time_to_transfer_seconds=999,
    checked_balance=True,
):
    """Build a minimal session context dict."""
    return {
        "on_phone_call": on_phone_call,
        "backspace_count": backspace_count,
        "amount_pasted": amount_pasted,
        "app_switch_count": app_switch_count,
        "time_to_transfer_seconds": time_to_transfer_seconds,
        "checked_balance": checked_balance,
    }


@pytest.fixture
def detector():
    return ScamVictimDetector()


@pytest.fixture
def engine():
    return DualRiskEngine()


# ═══════════════════════════════════════════════════════════════════════
# ScamVictimDetector Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWeights:
    def test_weights_sum_to_one(self):
        total = sum(ScamVictimDetector.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestSV01ActiveCall:
    """SV01: Active phone call during transaction."""

    def test_call_with_high_amount_new_beneficiary(self, detector):
        txn = _txn(amount=100_000, is_new_beneficiary=True)
        ctx = _session(on_phone_call=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["active_call"] == 1.0
        assert "SV01_ACTIVE_CALL" in result.reason_codes

    def test_call_with_high_amount_only(self, detector):
        txn = _txn(amount=100_000, is_new_beneficiary=False)
        ctx = _session(on_phone_call=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["active_call"] == 0.6

    def test_call_with_new_beneficiary_only(self, detector):
        txn = _txn(amount=10_000, is_new_beneficiary=True)
        ctx = _session(on_phone_call=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["active_call"] == 0.6

    def test_call_low_amount_existing_beneficiary(self, detector):
        txn = _txn(amount=5_000, is_new_beneficiary=False)
        ctx = _session(on_phone_call=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["active_call"] == 0.3

    def test_no_call(self, detector):
        txn = _txn(amount=100_000, is_new_beneficiary=True)
        ctx = _session(on_phone_call=False)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["active_call"] == 0.0


class TestSV02CoachedBehavior:
    """SV02: Coached session behavior — backspaces, paste, app-switching."""

    def test_all_indicators(self, detector):
        txn = _txn()
        ctx = _session(backspace_count=15, amount_pasted=True, app_switch_count=5)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 1.0
        assert "SV02_COACHED_BEHAVIOR" in result.reason_codes

    def test_two_indicators(self, detector):
        txn = _txn()
        ctx = _session(backspace_count=15, amount_pasted=True, app_switch_count=0)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 0.7

    def test_one_indicator_backspaces(self, detector):
        txn = _txn()
        ctx = _session(backspace_count=15)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 0.4

    def test_one_indicator_paste(self, detector):
        txn = _txn()
        ctx = _session(amount_pasted=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 0.4

    def test_one_indicator_app_switch(self, detector):
        txn = _txn()
        ctx = _session(app_switch_count=5)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 0.4

    def test_no_indicators(self, detector):
        txn = _txn()
        ctx = _session(backspace_count=2, amount_pasted=False, app_switch_count=1)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["coached_behavior"] == 0.0

    def test_coaching_indicators_in_result(self, detector):
        txn = _txn()
        ctx = _session(backspace_count=15, amount_pasted=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert len(result.coaching_indicators) > 0
        assert any("backspace" in ind.lower() for ind in result.coaching_indicators)


class TestSV03UnusualBeneficiaryAmount:
    """SV03: New beneficiary + unusual amount."""

    def test_new_beneficiary_high_amount(self, detector):
        history = [{"amount": 10_000}, {"amount": 8_000}, {"amount": 12_000}]
        avg = 10_000
        txn = _txn(amount=avg * 4, is_new_beneficiary=True)  # > 3x average
        result = detector.detect("ACC001", txn, account_history=history)
        assert result.score_breakdown["unusual_beneficiary_amount"] == 1.0
        assert "SV03_UNUSUAL_BENEFICIARY_AMOUNT" in result.reason_codes

    def test_new_beneficiary_moderate_amount(self, detector):
        history = [{"amount": 10_000}, {"amount": 10_000}]
        txn = _txn(amount=25_000, is_new_beneficiary=True)  # 2x-3x average
        result = detector.detect("ACC001", txn, account_history=history)
        assert result.score_breakdown["unusual_beneficiary_amount"] == 0.6

    def test_new_beneficiary_normal_amount(self, detector):
        history = [{"amount": 10_000}, {"amount": 10_000}]
        txn = _txn(amount=12_000, is_new_beneficiary=True)  # ~1.2x average
        result = detector.detect("ACC001", txn, account_history=history)
        assert result.score_breakdown["unusual_beneficiary_amount"] == 0.3

    def test_existing_beneficiary(self, detector):
        history = [{"amount": 10_000}]
        txn = _txn(amount=100_000, is_new_beneficiary=False)
        result = detector.detect("ACC001", txn, account_history=history)
        assert result.score_breakdown["unusual_beneficiary_amount"] == 0.0

    def test_new_beneficiary_no_history(self, detector):
        txn = _txn(amount=50_000, is_new_beneficiary=True)
        result = detector.detect("ACC001", txn, account_history=[])
        assert result.score_breakdown["unusual_beneficiary_amount"] == 0.4


class TestSV04Urgency:
    """SV04: Urgency indicators — rapid navigation, skipped balance check."""

    def test_very_rapid_transfer(self, detector):
        txn = _txn()
        ctx = _session(time_to_transfer_seconds=15)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["urgency_indicators"] >= 0.6

    def test_fast_transfer(self, detector):
        txn = _txn()
        ctx = _session(time_to_transfer_seconds=45)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["urgency_indicators"] == 0.3

    def test_skipped_balance_check(self, detector):
        txn = _txn()
        ctx = _session(checked_balance=False, time_to_transfer_seconds=999)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["urgency_indicators"] == 0.4

    def test_rapid_and_skipped_balance(self, detector):
        txn = _txn()
        ctx = _session(time_to_transfer_seconds=15, checked_balance=False)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["urgency_indicators"] == 1.0
        assert "SV04_URGENCY" in result.reason_codes

    def test_no_urgency(self, detector):
        txn = _txn()
        ctx = _session(time_to_transfer_seconds=120, checked_balance=True)
        result = detector.detect("ACC001", txn, session_context=ctx)
        assert result.score_breakdown["urgency_indicators"] == 0.0


class TestSV05Vulnerability:
    """SV05: Elderly / vulnerable sender."""

    def test_elderly_large_new_beneficiary(self, detector):
        account = {"account_holder_age": 72}
        txn = _txn(amount=100_000, is_new_beneficiary=True, account=account)
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["vulnerability"] == 1.0
        assert "SV05_ELDERLY_VULNERABILITY" in result.reason_codes

    def test_elderly_large_existing_beneficiary(self, detector):
        account = {"account_holder_age": 65}
        txn = _txn(amount=100_000, is_new_beneficiary=False, account=account)
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["vulnerability"] == 0.6

    def test_elderly_small_amount(self, detector):
        account = {"account_holder_age": 68}
        txn = _txn(amount=5_000, is_new_beneficiary=False, account=account)
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["vulnerability"] == 0.3

    def test_non_elderly(self, detector):
        account = {"account_holder_age": 35}
        txn = _txn(amount=100_000, is_new_beneficiary=True, account=account)
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["vulnerability"] == 0.0


class TestSV06ScamKeywords:
    """SV06: Known scam script patterns in narration."""

    def test_safe_account_keyword(self, detector):
        txn = _txn(narration="Transfer to safe account as directed")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.8
        assert "SV06_SCAM_KEYWORDS" in result.reason_codes

    def test_rbi_verification_keyword(self, detector):
        txn = _txn(narration="RBI verification required urgently")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.8

    def test_multiple_keywords(self, detector):
        txn = _txn(narration="Transfer to safe account for RBI verification")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 1.0

    def test_no_keywords(self, detector):
        txn = _txn(narration="Rent payment for March")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.0

    def test_empty_narration(self, detector):
        txn = _txn(narration="")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.0

    def test_case_insensitive(self, detector):
        txn = _txn(narration="TRANSFER FOR TAX REFUND")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.8

    def test_arrest_warrant_keyword(self, detector):
        txn = _txn(narration="Urgent: arrest warrant payment")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.8

    def test_lottery_keyword(self, detector):
        txn = _txn(narration="Lottery claim fee")
        result = detector.detect("ACC001", txn)
        assert result.score_breakdown["scam_keywords"] == 0.8


class TestInterventionMapping:
    """Test composite score to intervention level mapping."""

    def test_block(self, detector):
        # Engineer a scenario with very high scores across all signals
        account = {"account_holder_age": 72}
        txn = _txn(
            amount=200_000,
            is_new_beneficiary=True,
            narration="Transfer to safe account for RBI verification",
            account=account,
        )
        ctx = _session(
            on_phone_call=True,
            backspace_count=20,
            amount_pasted=True,
            app_switch_count=5,
            time_to_transfer_seconds=10,
            checked_balance=False,
        )
        history = [{"amount": 5_000}]
        result = detector.detect("ACC001", txn, ctx, history)
        assert result.recommended_intervention == "BLOCK"
        assert result.composite_score >= 0.8

    def test_delay(self, detector):
        # SV01 (1.0 * 0.20) + SV03 (1.0 * 0.20) + SV06 (0.8 * 0.15) = 0.52
        # Need higher: add SV02
        txn = _txn(amount=100_000, is_new_beneficiary=True)
        ctx = _session(
            on_phone_call=True,
            backspace_count=20,
            amount_pasted=True,
            app_switch_count=5,
        )
        history = [{"amount": 5_000}]
        result = detector.detect("ACC001", txn, ctx, history)
        assert result.composite_score >= 0.6
        assert result.recommended_intervention in ("DELAY", "BLOCK")

    def test_hard_warning(self, detector):
        # SV01 (1.0 * 0.20) + SV03 (0.4 * 0.20) = 0.28
        # add SV04: (1.0 * 0.15) = 0.15 → 0.43
        txn = _txn(amount=100_000, is_new_beneficiary=True)
        ctx = _session(
            on_phone_call=True,
            time_to_transfer_seconds=10,
            checked_balance=False,
        )
        result = detector.detect("ACC001", txn, ctx, account_history=[])
        assert result.composite_score >= 0.4
        assert result.recommended_intervention in ("HARD_WARNING", "DELAY", "BLOCK")

    def test_soft_warning(self, detector):
        # SV02 only, one indicator: 0.4 * 0.20 = 0.08
        # SV04 skipped balance: 0.4 * 0.15 = 0.06 → 0.14
        # Need at least 0.2... add new beneficiary no history: 0.4 * 0.20 = 0.08
        # total: 0.22
        txn = _txn(amount=10_000, is_new_beneficiary=True)
        ctx = _session(backspace_count=15, checked_balance=False)
        result = detector.detect("ACC001", txn, ctx, account_history=[])
        assert result.composite_score >= 0.2
        assert result.recommended_intervention in ("SOFT_WARNING", "HARD_WARNING")

    def test_none_intervention(self, detector):
        txn = _txn(amount=5_000, is_new_beneficiary=False, narration="Rent")
        ctx = _session()
        result = detector.detect("ACC001", txn, ctx)
        assert result.composite_score < 0.2
        assert result.recommended_intervention == "NONE"


class TestNoSessionContext:
    """Graceful handling when session_context is None."""

    def test_no_session_context(self, detector):
        txn = _txn(amount=10_000, is_new_beneficiary=False)
        result = detector.detect("ACC001", txn, session_context=None)
        assert isinstance(result, ScamVictimResult)
        assert result.score_breakdown["active_call"] == 0.0
        assert result.score_breakdown["coached_behavior"] == 0.0
        assert result.score_breakdown["urgency_indicators"] == 0.0

    def test_no_history(self, detector):
        txn = _txn(amount=10_000, is_new_beneficiary=False)
        result = detector.detect("ACC001", txn, account_history=None)
        assert isinstance(result, ScamVictimResult)
        assert result.score_breakdown["unusual_beneficiary_amount"] == 0.0


class TestResultImmutability:
    """Verify that ScamVictimResult is frozen."""

    def test_frozen(self, detector):
        txn = _txn()
        result = detector.detect("ACC001", txn)
        with pytest.raises(AttributeError):
            result.composite_score = 0.99


# ═══════════════════════════════════════════════════════════════════════
# DualRiskEngine Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDualRiskBothElevated:
    """Both sender (victim) and receiver (mule) scores are high."""

    def test_high_combined_risk(self, engine):
        sender = {"account_id": "SENDER01", "account_holder_age": 70}
        receiver = {"account_id": "RECV01"}
        txn = {
            "amount": 200_000,
            "is_new_beneficiary": True,
            "narration": "Transfer to safe account for RBI verification",
        }
        ctx = _session(on_phone_call=True, time_to_transfer_seconds=10, checked_balance=False)
        history = [{"amount": 5_000}]

        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            sender_history=history,
            receiver_mule_score=0.85,
        )
        assert result.combined_risk >= 0.8
        assert result.transaction_recommendation == "BLOCK_HARD"
        assert "DUAL_RISK_INTERACTION_BOOST" in result.reason_codes
        assert "RECEIVER_MULE_ELEVATED" in result.reason_codes


class TestDualRiskSenderOnly:
    """Only sender side is elevated."""

    def test_sender_elevated_receiver_low(self, engine):
        sender = {"account_id": "SENDER01"}
        receiver = {"account_id": "RECV01"}
        txn = {
            "amount": 100_000,
            "is_new_beneficiary": True,
            "narration": "Transfer to safe account",
        }
        ctx = _session(on_phone_call=True)

        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            receiver_mule_score=0.1,
        )
        # Sender victim score high, receiver low, no interaction boost
        assert result.combined_risk > 0.0
        assert "DUAL_RISK_INTERACTION_BOOST" not in result.reason_codes
        assert result.sender_risk.composite_score > 0.3


class TestDualRiskReceiverOnly:
    """Only receiver side is elevated."""

    def test_receiver_elevated_sender_low(self, engine):
        sender = {"account_id": "SENDER01"}
        receiver = {"account_id": "RECV01"}
        txn = {"amount": 5_000, "is_new_beneficiary": False, "narration": "Rent"}
        ctx = _session()

        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            receiver_mule_score=0.9,
        )
        # Sender score near zero, receiver high
        assert result.combined_risk > 0.0
        assert result.receiver_risk["mule_probability"] == 0.9
        assert "RECEIVER_MULE_ELEVATED" in result.reason_codes
        assert "DUAL_RISK_INTERACTION_BOOST" not in result.reason_codes


class TestDualRiskNeitherElevated:
    """Neither side elevated — should ALLOW."""

    def test_allow_low_risk(self, engine):
        sender = {"account_id": "SENDER01"}
        receiver = {"account_id": "RECV01"}
        txn = {"amount": 5_000, "is_new_beneficiary": False, "narration": "Rent"}
        ctx = _session()

        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            receiver_mule_score=0.0,
        )
        assert result.combined_risk < 0.25
        assert result.transaction_recommendation == "ALLOW"
        assert result.intervention_message == ""


class TestInterventionMessages:
    """Test contextual intervention message generation."""

    def test_scam_keywords_message(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {
            "amount": 100_000,
            "is_new_beneficiary": True,
            "narration": "Transfer to safe account",
        }
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            receiver_mule_score=0.5,
        )
        assert "safe account" in result.intervention_message.lower()
        assert "Banks never ask" in result.intervention_message

    def test_active_call_message(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {"amount": 100_000, "is_new_beneficiary": True, "narration": ""}
        ctx = _session(on_phone_call=True)
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            receiver_mule_score=0.5,
        )
        assert "phone" in result.intervention_message.lower()

    def test_elderly_message(self, engine):
        sender = {"account_id": "S1", "account_holder_age": 72}
        receiver = {"account_id": "R1"}
        txn = {"amount": 100_000, "is_new_beneficiary": True, "narration": ""}
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            receiver_mule_score=0.5,
        )
        assert "unusual transaction" in result.intervention_message.lower()

    def test_default_high_risk_message(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {"amount": 100_000, "is_new_beneficiary": True, "narration": ""}
        ctx = _session(
            backspace_count=20,
            amount_pasted=True,
            app_switch_count=5,
            time_to_transfer_seconds=10,
            checked_balance=False,
        )
        history = [{"amount": 5_000}]
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            sender_history=history,
            receiver_mule_score=0.5,
        )
        # Should have some intervention message (default)
        assert len(result.intervention_message) > 0

    def test_no_message_for_low_risk(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {"amount": 5_000, "is_new_beneficiary": False, "narration": ""}
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            receiver_mule_score=0.0,
        )
        assert result.intervention_message == ""


class TestRecommendationMapping:
    """Test combined risk to recommendation mapping."""

    def test_block_hard(self, engine):
        sender = {"account_id": "S1", "account_holder_age": 72}
        receiver = {"account_id": "R1"}
        txn = {
            "amount": 200_000,
            "is_new_beneficiary": True,
            "narration": "Transfer to safe account for RBI verification",
        }
        ctx = _session(
            on_phone_call=True,
            backspace_count=20,
            amount_pasted=True,
            app_switch_count=5,
            time_to_transfer_seconds=10,
            checked_balance=False,
        )
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            sender_history=[{"amount": 5_000}],
            receiver_mule_score=0.95,
        )
        assert result.transaction_recommendation == "BLOCK_HARD"

    def test_allow(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {"amount": 1_000, "is_new_beneficiary": False, "narration": ""}
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            receiver_mule_score=0.0,
        )
        assert result.transaction_recommendation == "ALLOW"


class TestDualRiskResultImmutability:
    """Verify DualRiskResult is frozen."""

    def test_frozen(self, engine):
        sender = {"account_id": "S1"}
        receiver = {"account_id": "R1"}
        txn = {"amount": 1_000, "is_new_beneficiary": False, "narration": ""}
        result = engine.evaluate_transaction(
            sender=sender, receiver=receiver, transaction=txn,
        )
        with pytest.raises(AttributeError):
            result.combined_risk = 0.99


class TestDualRiskCombinedScoreBounded:
    """Combined risk should always be in [0.0, 1.0]."""

    def test_combined_bounded(self, engine):
        sender = {"account_id": "S1", "account_holder_age": 80}
        receiver = {"account_id": "R1"}
        txn = {
            "amount": 500_000,
            "is_new_beneficiary": True,
            "narration": "safe account lottery prize customs arrest warrant",
        }
        ctx = _session(
            on_phone_call=True,
            backspace_count=50,
            amount_pasted=True,
            app_switch_count=10,
            time_to_transfer_seconds=5,
            checked_balance=False,
        )
        result = engine.evaluate_transaction(
            sender=sender,
            receiver=receiver,
            transaction=txn,
            session_context=ctx,
            sender_history=[{"amount": 1_000}],
            receiver_mule_score=1.0,
        )
        assert 0.0 <= result.combined_risk <= 1.0
