"""Tests for transaction semantics analyzer."""

import pytest

from models.semantics.transaction_analyzer import (
    SIGNAL_WEIGHTS,
    SemanticsResult,
    TransactionSemanticsAnalyzer,
)


@pytest.fixture
def analyzer():
    return TransactionSemanticsAnalyzer()


def _txn(from_acc="A", to_acc="B", amount=10000, narration="", to_upi="", merchant_id=""):
    return {
        "from_account": from_acc,
        "to_account": to_acc,
        "amount": amount,
        "timestamp": "2024-01-15T10:00:00",
        "narration": narration,
        "to_upi": to_upi,
        "merchant_id": merchant_id,
    }


class TestSemanticsResult:
    def test_frozen(self):
        r = SemanticsResult("A", 0.0, 0.0, 0.0, 0.0, 0.0, ())
        with pytest.raises(AttributeError):
            r.composite_score = 0.5


class TestSignalWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 0.001


class TestTS01RoundAmounts:
    def test_structuring_near_threshold(self, analyzer):
        txns = [_txn(amount=45000) for _ in range(5)]
        result = analyzer.analyze("A", txns)
        assert result.round_amount_score > 0.3
        assert any("TS01" in rc for rc in result.reason_codes)

    def test_normal_amounts(self, analyzer):
        txns = [_txn(amount=12345), _txn(amount=7891), _txn(amount=23456)]
        result = analyzer.analyze("A", txns)
        assert result.round_amount_score < 0.3


class TestTS02UPIPatterns:
    def test_numeric_heavy_upi(self, analyzer):
        txns = [_txn(to_upi="9876543210123@ybl") for _ in range(5)]
        result = analyzer.analyze("A", txns)
        assert result.upi_pattern_score > 0.3
        assert any("TS02" in rc for rc in result.reason_codes)

    def test_normal_upi(self, analyzer):
        txns = [_txn(to_upi="john.doe@paytm") for _ in range(5)]
        result = analyzer.analyze("A", txns)
        assert result.upi_pattern_score == 0.0


class TestTS03Narrations:
    def test_suspicious_keywords(self, analyzer):
        txns = [
            _txn(narration="crypto investment return"),
            _txn(narration="commission payment"),
            _txn(narration="telegram job payment"),
        ]
        result = analyzer.analyze("A", txns)
        assert result.narration_score > 0.3
        assert any("TS03" in rc for rc in result.reason_codes)

    def test_normal_narrations(self, analyzer):
        txns = [
            _txn(narration="rent payment"),
            _txn(narration="grocery shopping"),
        ]
        result = analyzer.analyze("A", txns)
        assert result.narration_score == 0.0


class TestTS04CryptoGaming:
    def test_crypto_merchant(self, analyzer):
        txns = [
            _txn(merchant_id="wazirx_exchange"),
            _txn(merchant_id="wazirx_exchange"),
            _txn(merchant_id="coindcx_wallet"),
        ]
        result = analyzer.analyze("A", txns)
        assert result.crypto_gaming_score > 0.3
        assert any("TS04" in rc for rc in result.reason_codes)

    def test_gaming_merchant(self, analyzer):
        txns = [
            _txn(narration="dream11 deposit"),
            _txn(narration="dream11 deposit"),
            _txn(narration="mpl game entry"),
        ]
        result = analyzer.analyze("A", txns)
        assert result.crypto_gaming_score > 0.3

    def test_no_crypto_gaming(self, analyzer):
        txns = [_txn(merchant_id="grocery_store"), _txn(merchant_id="petrol_pump")]
        result = analyzer.analyze("A", txns)
        assert result.crypto_gaming_score == 0.0


class TestComposite:
    def test_composite_bounded(self, analyzer):
        txns = [
            _txn(
                amount=45000,
                narration="crypto commission",
                to_upi="9876543210123@ybl",
                merchant_id="wazirx",
            )
            for _ in range(10)
        ]
        result = analyzer.analyze("A", txns)
        assert 0.0 <= result.composite_score <= 1.0

    def test_no_outgoing(self, analyzer):
        txns = [_txn(from_acc="OTHER", to_acc="A")]
        result = analyzer.analyze("A", txns)
        assert result.composite_score == 0.0

    def test_empty_transactions(self, analyzer):
        result = analyzer.analyze("A", [])
        assert result.composite_score == 0.0


class TestBatchAnalysis:
    def test_batch(self, analyzer):
        accounts = [{"account_id": "A"}, {"account_id": "B"}]
        txns = [_txn(from_acc="A"), _txn(from_acc="B")]
        results = analyzer.analyze_batch(accounts, txns)
        assert "A" in results
        assert "B" in results
