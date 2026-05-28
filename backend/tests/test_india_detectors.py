"""
Comprehensive tests for India-specific detectors.

Covers:
  - FRI mobile risk scorer (VERY_HIGH, HIGH, MEDIUM, LOW, CLEAN, UNKNOWN)
  - Jan Dhan detector (JD01-JD04)
  - Crypto/Gaming detector (CH01-CH05)
  - UPI Compliance monitor (UC01-UC05, should_delay_payment)
  - Edge cases: empty transactions, missing fields
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from datetime import datetime

from models.india.fri_scorer import FRIClient, FRIRiskLevel, FRIResult
from models.india.jan_dhan_detector import JanDhanDetector, JanDhanRiskResult
from models.india.crypto_gaming_detector import CryptoGamingDetector, CryptoHawalaResult
from models.india.upi_compliance import UPIComplianceMonitor, UPIComplianceResult


# ═══════════════════════════════════════════════════════════════════════
# FRI Scorer Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFRIClient:
    """Tests for FRI mobile risk scoring."""

    def setup_method(self):
        self.client = FRIClient(demo_mode=True)

    def test_very_high_risk_ending_0000(self):
        """Numbers ending in 0000-0009 should be VERY_HIGH."""
        result = self.client.query_mobile_risk("9876540000")
        assert result.risk_level == FRIRiskLevel.VERY_HIGH
        assert result.score == 0.95
        assert result.source == "MOCK"
        assert result.citizen_reports >= 15
        assert result.ncrp_complaints >= 8

    def test_very_high_risk_ending_0005(self):
        result = self.client.query_mobile_risk("9876540005")
        assert result.risk_level == FRIRiskLevel.VERY_HIGH
        assert result.score == 0.95

    def test_high_risk_ending_1000(self):
        """Numbers ending in 1000-1999 should be HIGH."""
        result = self.client.query_mobile_risk("9876541000")
        assert result.risk_level == FRIRiskLevel.HIGH
        assert result.score == 0.75
        assert result.citizen_reports >= 5
        assert result.ncrp_complaints >= 2

    def test_high_risk_ending_1500(self):
        result = self.client.query_mobile_risk("9876541500")
        assert result.risk_level == FRIRiskLevel.HIGH

    def test_medium_risk_ending_2000(self):
        """Numbers ending in 2000-2999 should be MEDIUM."""
        result = self.client.query_mobile_risk("9876542000")
        assert result.risk_level == FRIRiskLevel.MEDIUM
        assert result.score == 0.50

    def test_low_risk_ending_3000(self):
        """Numbers ending in 3000-3999 should be LOW."""
        result = self.client.query_mobile_risk("9876543000")
        assert result.risk_level == FRIRiskLevel.LOW
        assert result.score == 0.25

    def test_clean_normal_number(self):
        """Numbers not matching any pattern should be CLEAN."""
        result = self.client.query_mobile_risk("9876545678")
        assert result.risk_level == FRIRiskLevel.CLEAN
        assert result.score == 0.05
        assert result.citizen_reports == 0
        assert result.ncrp_complaints == 0

    def test_unknown_for_invalid_number(self):
        """Invalid numbers should return UNKNOWN."""
        result = self.client.query_mobile_risk("12345")
        assert result.risk_level == FRIRiskLevel.UNKNOWN
        assert result.score == 0.0
        assert result.source == "UNAVAILABLE"

    def test_strips_plus91_prefix(self):
        """Should handle +91 prefix correctly."""
        result = self.client.query_mobile_risk("+919876545678")
        assert result.risk_level == FRIRiskLevel.CLEAN
        assert result.mobile_number == "9876545678"

    def test_strips_91_prefix(self):
        result = self.client.query_mobile_risk("919876545678")
        assert result.risk_level == FRIRiskLevel.CLEAN

    def test_strips_leading_zero(self):
        result = self.client.query_mobile_risk("09876545678")
        assert result.risk_level == FRIRiskLevel.CLEAN

    def test_result_is_frozen(self):
        """FRIResult should be immutable."""
        result = self.client.query_mobile_risk("9876545678")
        with pytest.raises(AttributeError):
            result.score = 0.99  # type: ignore[misc]

    def test_live_mode_returns_unknown(self):
        """Live mode without real API returns UNKNOWN gracefully."""
        live_client = FRIClient(demo_mode=False)
        result = live_client.query_mobile_risk("9876545678")
        assert result.risk_level == FRIRiskLevel.UNKNOWN
        assert result.source == "UNAVAILABLE"

    def test_last_updated_is_iso(self):
        result = self.client.query_mobile_risk("9876545678")
        # Should parse without error
        datetime.fromisoformat(result.last_updated)


# ═══════════════════════════════════════════════════════════════════════
# Jan Dhan Detector Tests
# ═══════════════════════════════════════════════════════════════════════

class TestJanDhanDetector:
    """Tests for Jan Dhan / BSBDA risk detection."""

    def setup_method(self):
        self.detector = JanDhanDetector()

    def _bsbda_account(self, acc_id="JD001", **overrides):
        base = {
            "account_id": acc_id,
            "account_type": "BSBDA",
            "city": "patna",
            "days_since_last_txn": 0,
        }
        base.update(overrides)
        return base

    def _jan_dhan_account(self, acc_id="JD002", **overrides):
        base = {
            "account_id": acc_id,
            "account_type": "SAVINGS",
            "is_jan_dhan": True,
            "city": "ranchi",
            "days_since_last_txn": 0,
        }
        base.update(overrides)
        return base

    @staticmethod
    def _txn(
        from_acc="SRC",
        to_acc="JD001",
        amount=5000,
        ts="2024-06-15T10:00:00",
        **kwargs,
    ):
        base = {
            "from_account": from_acc,
            "to_account": to_acc,
            "amount": amount,
            "timestamp": ts,
        }
        base.update(kwargs)
        return base

    # ── JD01: Volume spike ──────────────────────────────────────────

    def test_jd01_high_volume_triggers(self):
        """BSBDA with >10 txns in 24h should trigger JD01."""
        acc = self._bsbda_account()
        txns = [
            self._txn(ts=f"2024-06-15T{10 + i}:00:00")
            for i in range(15)
        ]
        result = self.detector.assess(acc, txns)
        assert result.is_bsbda is True
        assert result.activity_spike_score > 0.0
        assert any("JD01" in r for r in result.reason_codes)

    def test_jd01_below_threshold(self):
        """BSBDA with <=10 txns in 24h should not trigger JD01."""
        acc = self._bsbda_account()
        txns = [self._txn(ts=f"2024-06-15T{10 + i}:00:00") for i in range(5)]
        result = self.detector.assess(acc, txns)
        assert not any("JD01" in r for r in result.reason_codes)

    def test_jd01_non_bsbda_no_trigger(self):
        """Non-BSBDA accounts should not trigger JD01."""
        acc = {"account_id": "REG001", "account_type": "SAVINGS"}
        txns = [self._txn(ts=f"2024-06-15T{10 + i}:00:00") for i in range(15)]
        result = self.detector.assess(acc, txns)
        assert not any("JD01" in r for r in result.reason_codes)

    # ── JD02: Dormancy burst ────────────────────────────────────────

    def test_jd02_dormant_then_active(self):
        """Dormant >90 days with sudden activity should trigger JD02."""
        acc = self._bsbda_account(days_since_last_txn=120)
        txns = [self._txn(ts=f"2024-06-15T{10 + i}:00:00") for i in range(8)]
        result = self.detector.assess(acc, txns)
        assert any("JD02" in r for r in result.reason_codes)

    def test_jd02_not_dormant(self):
        """Recently active account should not trigger JD02."""
        acc = self._bsbda_account(days_since_last_txn=10)
        txns = [self._txn(ts=f"2024-06-15T{10 + i}:00:00") for i in range(8)]
        result = self.detector.assess(acc, txns)
        assert not any("JD02" in r for r in result.reason_codes)

    def test_jd02_dormant_few_txns(self):
        """Dormant account with only 2 txns should not trigger JD02."""
        acc = self._bsbda_account(days_since_last_txn=120)
        txns = [self._txn(), self._txn(ts="2024-06-15T11:00:00")]
        result = self.detector.assess(acc, txns)
        assert not any("JD02" in r for r in result.reason_codes)

    # ── JD03: Tier-1 inflows ────────────────────────────────────────

    def test_jd03_multiple_tier1_inflows(self):
        """BSBDA receiving from >= 3 tier-1 city accounts should trigger JD03."""
        acc = self._bsbda_account()
        txns = [
            self._txn(from_acc=f"MUM{i}", sender_city="mumbai")
            for i in range(4)
        ]
        result = self.detector.assess(acc, txns)
        assert any("JD03" in r for r in result.reason_codes)

    def test_jd03_few_tier1_no_trigger(self):
        """BSBDA with <3 tier-1 senders should not trigger JD03."""
        acc = self._bsbda_account()
        txns = [
            self._txn(from_acc="MUM1", sender_city="mumbai"),
            self._txn(from_acc="DEL1", sender_city="delhi"),
        ]
        result = self.detector.assess(acc, txns)
        assert not any("JD03" in r for r in result.reason_codes)

    def test_jd03_non_bsbda_no_trigger(self):
        """Non-BSBDA should not trigger JD03 even with many tier-1 inflows."""
        acc = {"account_id": "REG001", "account_type": "SAVINGS"}
        txns = [
            self._txn(from_acc=f"MUM{i}", to_acc="REG001", sender_city="mumbai")
            for i in range(5)
        ]
        result = self.detector.assess(acc, txns)
        assert not any("JD03" in r for r in result.reason_codes)

    # ── JD04: Urban mismatch ────────────────────────────────────────

    def test_jd04_tier2_to_urban(self):
        """Tier-2/3 account transacting with >= 2 urban accounts triggers JD04."""
        acc = self._bsbda_account(city="patna")
        txns = [
            self._txn(from_acc="MUM1", counterparty_city="mumbai"),
            self._txn(from_acc="DEL1", counterparty_city="delhi"),
            self._txn(from_acc="BLR1", counterparty_city="bangalore"),
        ]
        result = self.detector.assess(acc, txns)
        assert any("JD04" in r for r in result.reason_codes)

    def test_jd04_tier1_account_no_trigger(self):
        """Tier-1 city accounts should not trigger JD04."""
        acc = self._bsbda_account(city="mumbai")
        txns = [
            self._txn(from_acc="DEL1", counterparty_city="delhi"),
            self._txn(from_acc="BLR1", counterparty_city="bangalore"),
        ]
        result = self.detector.assess(acc, txns)
        assert not any("JD04" in r for r in result.reason_codes)

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_transactions(self):
        acc = self._bsbda_account()
        result = self.detector.assess(acc, [])
        assert result.composite_score == 0.0
        assert result.reason_codes == ()

    def test_missing_fields(self):
        """Account with minimal fields should not crash."""
        acc = {"account_id": "MINIMAL"}
        result = self.detector.assess(acc, [{"amount": 1000}])
        assert isinstance(result, JanDhanRiskResult)
        assert result.composite_score >= 0.0

    def test_result_is_frozen(self):
        acc = self._bsbda_account()
        result = self.detector.assess(acc, [])
        with pytest.raises(AttributeError):
            result.composite_score = 0.99  # type: ignore[misc]

    def test_jan_dhan_flag_detected(self):
        """is_jan_dhan=True should be detected as BSBDA."""
        acc = self._jan_dhan_account()
        result = self.detector.assess(acc, [])
        assert result.is_bsbda is True

    def test_composite_bounded(self):
        """Composite score should be between 0 and 1."""
        acc = self._bsbda_account(days_since_last_txn=120, city="patna")
        txns = [
            self._txn(
                from_acc=f"MUM{i}",
                ts=f"2024-06-15T{10 + i}:00:00",
                sender_city="mumbai",
                counterparty_city="mumbai",
            )
            for i in range(20)
        ]
        result = self.detector.assess(acc, txns)
        assert 0.0 <= result.composite_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# Crypto/Gaming Detector Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCryptoGamingDetector:
    """Tests for crypto, gaming, and hawala detection."""

    def setup_method(self):
        self.detector = CryptoGamingDetector()

    @staticmethod
    def _acc(acc_id="CG001"):
        return {"account_id": acc_id}

    @staticmethod
    def _txn(amount=10000, merchant_id="", upi_handle="", **kwargs):
        base = {
            "amount": amount,
            "merchant_id": merchant_id,
            "upi_handle": upi_handle,
            "from_account": "SRC",
            "to_account": "DST",
        }
        base.update(kwargs)
        return base

    # ── CH01: Crypto merchants ──────────────────────────────────────

    def test_ch01_wazirx_detected(self):
        txns = [self._txn(merchant_id="WAZIRX_PAY")]
        result = self.detector.assess(self._acc(), txns)
        assert result.crypto_score > 0.0
        assert "wazirx" in result.flagged_merchants
        assert any("CH01" in r for r in result.reason_codes)

    def test_ch01_multiple_crypto(self):
        txns = [
            self._txn(merchant_id="wazirx_deposit"),
            self._txn(upi_handle="pay@coindcx"),
            self._txn(merchant_id="zebpay_in"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert len(result.flagged_merchants) >= 3
        assert result.crypto_score > 0.0

    def test_ch01_no_crypto(self):
        txns = [self._txn(merchant_id="amazon"), self._txn(merchant_id="flipkart")]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH01" in r for r in result.reason_codes)

    def test_ch01_upi_handle_match(self):
        txns = [self._txn(upi_handle="deposit@coinswitch")]
        result = self.detector.assess(self._acc(), txns)
        assert "coinswitch" in result.flagged_merchants

    # ── CH02: P2P crypto amounts ────────────────────────────────────

    def test_ch02_usdt_pattern_detected(self):
        """Multiple transactions at USDT-equivalent amounts should trigger CH02."""
        txns = [
            self._txn(amount=8300),     # ~$100 USDT
            self._txn(amount=8250),     # within 5% tolerance
            self._txn(amount=41500),    # ~$500 USDT
        ]
        result = self.detector.assess(self._acc(), txns)
        assert any("CH02" in r for r in result.reason_codes)

    def test_ch02_single_match_no_trigger(self):
        """Single matching amount should not trigger (need >=2)."""
        txns = [self._txn(amount=8300)]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH02" in r for r in result.reason_codes)

    def test_ch02_random_amounts_no_trigger(self):
        txns = [self._txn(amount=5000), self._txn(amount=12000)]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH02" in r for r in result.reason_codes)

    # ── CH03: Gaming merchants ──────────────────────────────────────

    def test_ch03_dream11_detected(self):
        txns = [self._txn(merchant_id="dream11_wallet")]
        result = self.detector.assess(self._acc(), txns)
        assert result.gaming_score > 0.0
        assert "dream11" in result.flagged_merchants
        assert any("CH03" in r for r in result.reason_codes)

    def test_ch03_betting_platforms(self):
        txns = [
            self._txn(merchant_id="1xbet_deposit"),
            self._txn(upi_handle="pay@betway"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert result.gaming_score > 0.0
        assert "1xbet" in result.flagged_merchants
        assert "betway" in result.flagged_merchants

    def test_ch03_no_gaming(self):
        txns = [self._txn(merchant_id="swiggy"), self._txn(merchant_id="zomato")]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH03" in r for r in result.reason_codes)

    # ── CH04: Hawala-digital hybrid ─────────────────────────────────

    def test_ch04_cash_then_upi_fanout(self):
        """Cash deposits followed by UPI fan-out to multiple accounts."""
        txns = [
            self._txn(amount=100000, channel="CASH", direction="INBOUND"),
            self._txn(amount=25000, channel="UPI", to_account="D1", direction="OUTBOUND"),
            self._txn(amount=25000, channel="UPI", to_account="D2", direction="OUTBOUND"),
            self._txn(amount=25000, channel="UPI", to_account="D3", direction="OUTBOUND"),
            self._txn(amount=20000, channel="UPI", to_account="D4", direction="OUTBOUND"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert result.hawala_score > 0.0
        assert any("CH04" in r for r in result.reason_codes)

    def test_ch04_no_cash_deposits(self):
        """Without cash deposits, CH04 should not trigger."""
        txns = [
            self._txn(amount=25000, channel="UPI", to_account="D1", direction="OUTBOUND"),
            self._txn(amount=25000, channel="UPI", to_account="D2", direction="OUTBOUND"),
            self._txn(amount=25000, channel="UPI", to_account="D3", direction="OUTBOUND"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH04" in r for r in result.reason_codes)

    def test_ch04_few_upi_recipients(self):
        """Cash deposit but UPI to fewer than 3 recipients: no trigger."""
        txns = [
            self._txn(amount=100000, channel="CASH", direction="INBOUND"),
            self._txn(amount=50000, channel="UPI", to_account="D1", direction="OUTBOUND"),
            self._txn(amount=50000, channel="UPI", to_account="D2", direction="OUTBOUND"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH04" in r for r in result.reason_codes)

    # ── CH05: Circular gaming flow ──────────────────────────────────

    def test_ch05_deposit_and_withdraw(self):
        """Deposit to gaming wallet, minimal play, withdraw should trigger CH05."""
        txns = [
            self._txn(
                amount=50000, category="gaming",
                direction="OUTBOUND", merchant_id="gaming_wallet",
            ),
            self._txn(
                amount=48000, category="gaming",
                direction="INBOUND", merchant_id="gaming_wallet",
            ),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert any("CH05" in r for r in result.reason_codes)

    def test_ch05_low_recovery_no_trigger(self):
        """Significant loss in gaming should not trigger CH05."""
        txns = [
            self._txn(
                amount=50000, category="gaming",
                direction="OUTBOUND", merchant_id="gaming_wallet",
            ),
            self._txn(
                amount=10000, category="gaming",
                direction="INBOUND", merchant_id="gaming_wallet",
            ),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert not any("CH05" in r for r in result.reason_codes)

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_transactions(self):
        result = self.detector.assess(self._acc(), [])
        assert result.composite_score == 0.0
        assert result.flagged_merchants == ()

    def test_missing_merchant_fields(self):
        """Transactions without merchant_id or upi_handle should not crash."""
        txns = [{"amount": 1000, "from_account": "A", "to_account": "B"}]
        result = self.detector.assess(self._acc(), txns)
        assert isinstance(result, CryptoHawalaResult)

    def test_result_is_frozen(self):
        result = self.detector.assess(self._acc(), [])
        with pytest.raises(AttributeError):
            result.composite_score = 0.99  # type: ignore[misc]

    def test_composite_bounded(self):
        txns = [
            self._txn(merchant_id="wazirx", amount=8300, channel="CASH", direction="INBOUND"),
            self._txn(merchant_id="dream11", amount=41500, channel="UPI", to_account="D1", direction="OUTBOUND"),
            self._txn(merchant_id="1xbet", amount=8300, channel="UPI", to_account="D2", direction="OUTBOUND"),
            self._txn(amount=8250, channel="UPI", to_account="D3", direction="OUTBOUND"),
        ]
        result = self.detector.assess(self._acc(), txns)
        assert 0.0 <= result.composite_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# UPI Compliance Monitor Tests
# ═══════════════════════════════════════════════════════════════════════

class TestUPIComplianceMonitor:
    """Tests for UPI regulatory compliance monitoring."""

    def setup_method(self):
        self.monitor = UPIComplianceMonitor()

    @staticmethod
    def _acc(acc_id="UPI001", **overrides):
        base = {
            "account_id": acc_id,
            "known_beneficiaries": ["BEN1", "BEN2", "BEN3"],
        }
        base.update(overrides)
        return base

    @staticmethod
    def _txn(
        amount=5000,
        channel="UPI",
        direction="OUTBOUND",
        upi_type="PAY",
        **kwargs,
    ):
        base = {
            "amount": amount,
            "channel": channel,
            "direction": direction,
            "upi_type": upi_type,
            "from_account": "SRC",
            "to_account": "DST",
            "timestamp": "2024-06-15T10:00:00",
        }
        base.update(kwargs)
        return base

    # ── UC01: Annual ceiling ────────────────────────────────────────

    def test_uc01_near_ceiling(self):
        """Annual UPI credit near Rs 25 lakh should trigger UC01."""
        txns = [
            self._txn(amount=500_000, direction="INBOUND") for _ in range(4)
        ]
        # 4 * 500k = 2M = 80% of 2.5M ceiling
        result = self.monitor.assess(self._acc(), txns)
        assert any("UC01" in f for f in result.flags)
        assert result.limit_proximity_pct > 70.0

    def test_uc01_below_threshold(self):
        """Annual UPI credit well below 70% should not trigger UC01."""
        txns = [self._txn(amount=10_000, direction="INBOUND") for _ in range(5)]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC01" in f for f in result.flags)

    def test_uc01_at_ceiling(self):
        """Annual UPI credit at or above ceiling should have max proximity."""
        txns = [self._txn(amount=2_500_000, direction="INBOUND")]
        result = self.monitor.assess(self._acc(), txns)
        assert result.limit_proximity_pct == 100.0

    # ── UC02: Cooling period flag ───────────────────────────────────

    def test_uc02_large_transactions(self):
        """Transactions >= Rs 10,000 should trigger UC02."""
        txns = [
            self._txn(amount=15_000),
            self._txn(amount=20_000),
            self._txn(amount=50_000),
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert any("UC02" in f for f in result.flags)
        assert result.cooling_period_applicable is True

    def test_uc02_small_transactions(self):
        """Transactions below Rs 10,000 should not trigger UC02."""
        txns = [self._txn(amount=5000), self._txn(amount=3000)]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC02" in f for f in result.flags)

    # ── UC03: New beneficiary + large transfer ──────────────────────

    def test_uc03_new_beneficiary_large_transfer(self):
        """Large transfer to unknown beneficiary should trigger UC03."""
        acc = self._acc(known_beneficiaries=["BEN1", "BEN2"])
        txns = [
            self._txn(amount=50_000, to_account="NEW_BEN"),
        ]
        result = self.monitor.assess(acc, txns)
        assert any("UC03" in f for f in result.flags)

    def test_uc03_known_beneficiary_no_trigger(self):
        """Large transfer to known beneficiary should not trigger UC03."""
        acc = self._acc(known_beneficiaries=["BEN1"])
        txns = [self._txn(amount=50_000, to_account="BEN1")]
        result = self.monitor.assess(acc, txns)
        assert not any("UC03" in f for f in result.flags)

    def test_uc03_new_beneficiary_small_amount_no_trigger(self):
        """Small transfer to new beneficiary should not trigger UC03."""
        acc = self._acc(known_beneficiaries=["BEN1"])
        txns = [self._txn(amount=5000, to_account="NEW_BEN")]
        result = self.monitor.assess(acc, txns)
        assert not any("UC03" in f for f in result.flags)

    # ── UC04: Collect request abuse ─────────────────────────────────

    def test_uc04_multiple_collects_same_handle(self):
        """>=3 collect requests from same handle should trigger UC04."""
        txns = [
            self._txn(upi_type="COLLECT", upi_handle="scammer@upi")
            for _ in range(5)
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert any("UC04" in f for f in result.flags)

    def test_uc04_few_collects_no_trigger(self):
        """<3 collect requests should not trigger UC04."""
        txns = [
            self._txn(upi_type="COLLECT", upi_handle="merchant@upi"),
            self._txn(upi_type="COLLECT", upi_handle="merchant@upi"),
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC04" in f for f in result.flags)

    def test_uc04_different_handles_no_trigger(self):
        """Collect requests from different handles should not trigger UC04."""
        txns = [
            self._txn(upi_type="COLLECT", upi_handle="a@upi"),
            self._txn(upi_type="COLLECT", upi_handle="b@upi"),
            self._txn(upi_type="COLLECT", upi_handle="c@upi"),
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC04" in f for f in result.flags)

    # ── UC05: P2P collect migration ─────────────────────────────────

    def test_uc05_collect_dominated(self):
        """>60% collect-initiated should trigger UC05."""
        txns = [
            self._txn(upi_type="COLLECT") for _ in range(7)
        ] + [
            self._txn(upi_type="PAY") for _ in range(3)
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert any("UC05" in f for f in result.flags)

    def test_uc05_pay_dominated_no_trigger(self):
        """PAY-dominated transactions should not trigger UC05."""
        txns = [
            self._txn(upi_type="PAY") for _ in range(8)
        ] + [
            self._txn(upi_type="COLLECT") for _ in range(2)
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC05" in f for f in result.flags)

    def test_uc05_too_few_transactions_no_trigger(self):
        """Fewer than 5 total should not trigger UC05."""
        txns = [self._txn(upi_type="COLLECT") for _ in range(3)]
        result = self.monitor.assess(self._acc(), txns)
        assert not any("UC05" in f for f in result.flags)

    # ── should_delay_payment ────────────────────────────────────────

    def test_should_delay_new_beneficiary_large(self):
        """New beneficiary + large amount should recommend delay."""
        txn = {"amount": 25000, "channel": "UPI", "to_account": "UNKNOWN_BEN"}
        acc = self._acc(known_beneficiaries=["BEN1"])
        should, reason = self.monitor.should_delay_payment(txn, acc, [])
        assert should is True
        assert "New beneficiary" in reason

    def test_should_not_delay_known_beneficiary(self):
        """Known beneficiary should not be delayed."""
        txn = {"amount": 25000, "channel": "UPI", "to_account": "BEN1"}
        acc = self._acc(known_beneficiaries=["BEN1"])
        should, reason = self.monitor.should_delay_payment(txn, acc, [])
        assert should is False

    def test_should_delay_rapid_large_payments(self):
        """Multiple recent large UPI payments should trigger delay."""
        txn = {"amount": 15000, "channel": "UPI", "to_account": "BEN1"}
        acc = self._acc(known_beneficiaries=["BEN1"])
        recent = [
            {"amount": 15000, "channel": "UPI"},
            {"amount": 20000, "channel": "UPI"},
            {"amount": 12000, "channel": "UPI"},
        ]
        should, reason = self.monitor.should_delay_payment(txn, acc, recent)
        assert should is True
        assert "large UPI payments" in reason

    def test_should_not_delay_non_upi(self):
        """Non-UPI channel should not be delayed."""
        txn = {"amount": 50000, "channel": "NEFT", "to_account": "UNKNOWN"}
        acc = self._acc()
        should, reason = self.monitor.should_delay_payment(txn, acc, [])
        assert should is False
        assert reason == ""

    def test_should_not_delay_small_amount(self):
        """Small amounts should not trigger delay."""
        txn = {"amount": 5000, "channel": "UPI", "to_account": "UNKNOWN_BEN"}
        acc = self._acc(known_beneficiaries=["BEN1"])
        should, reason = self.monitor.should_delay_payment(txn, acc, [])
        assert should is False

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_transactions(self):
        result = self.monitor.assess(self._acc(), [])
        assert result.composite_score == 0.0
        assert result.flags == ()

    def test_non_upi_transactions_ignored(self):
        """Non-UPI transactions should be filtered out."""
        txns = [
            {"amount": 500000, "channel": "NEFT", "direction": "INBOUND"},
            {"amount": 500000, "channel": "RTGS", "direction": "INBOUND"},
        ]
        result = self.monitor.assess(self._acc(), txns)
        assert result.annual_upi_credit == 0.0
        assert result.composite_score == 0.0

    def test_result_is_frozen(self):
        result = self.monitor.assess(self._acc(), [])
        with pytest.raises(AttributeError):
            result.composite_score = 0.99  # type: ignore[misc]

    def test_composite_bounded(self):
        """Composite score should always be 0-1."""
        txns = (
            [self._txn(amount=500_000, direction="INBOUND") for _ in range(5)]
            + [self._txn(amount=50_000, to_account="NEW1")]
            + [self._txn(amount=50_000, to_account="NEW2")]
            + [self._txn(upi_type="COLLECT", upi_handle="spam@upi") for _ in range(5)]
        )
        result = self.monitor.assess(self._acc(known_beneficiaries=[]), txns)
        assert 0.0 <= result.composite_score <= 1.0

    def test_missing_fields(self):
        """Transactions with missing fields should not crash."""
        txns = [{"amount": 1000}]
        result = self.monitor.assess({"account_id": "MIN"}, txns)
        assert isinstance(result, UPIComplianceResult)
