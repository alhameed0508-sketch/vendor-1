"""Tests for enhanced behavioral baseline signals (BL01-BL08)."""

from models.behavioral.baseline import compute_baselines, WEIGHTS


def _acc(acc_id, age=30, avg_monthly=8, kyc="VERIFIED"):
    return {
        "account_id": acc_id,
        "account_age_days": age,
        "avg_monthly_txn": avg_monthly,
        "kyc_status": kyc,
    }


def _txn(from_acc, to_acc, amount=10000, ts="2024-01-15T10:00:00"):
    return {
        "from_account": from_acc,
        "to_account": to_acc,
        "amount": amount,
        "timestamp": ts,
    }


class TestWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


class TestVolumeDeviation:
    def test_high_volume(self):
        accounts = [_acc("A", avg_monthly=2)]
        txns = [_txn("A", f"B{i}") for i in range(20)]
        result = compute_baselines(accounts, txns)
        assert result["A"].volume_deviation > 0.5

    def test_normal_volume(self):
        accounts = [_acc("A", avg_monthly=20)]
        txns = [_txn("A", "B") for _ in range(5)]
        result = compute_baselines(accounts, txns)
        assert result["A"].volume_deviation < 0.5


class TestBalanceRetention:
    def test_pass_through_account(self):
        accounts = [_acc("M")]
        in_txns = [_txn("S", "M", 100000)]
        out_txns = [_txn("M", "D", 95000)]
        txns = in_txns + out_txns
        result = compute_baselines(accounts, txns)
        assert result["M"].balance_retention > 0.5

    def test_retaining_account(self):
        accounts = [_acc("N")]
        txns = [_txn("S", "N", 100000), _txn("N", "D", 10000)]
        result = compute_baselines(accounts, txns)
        assert result["N"].balance_retention < 0.5


class TestBeneficiaryEntropy:
    def test_high_entropy_many_recipients(self):
        accounts = [_acc("A")]
        txns = [_txn("A", f"R{i}", 10000) for i in range(10)]
        result = compute_baselines(accounts, txns)
        assert result["A"].beneficiary_entropy > 0.5

    def test_low_entropy_single_recipient(self):
        accounts = [_acc("A")]
        txns = [_txn("A", "B", 10000) for _ in range(10)]
        result = compute_baselines(accounts, txns)
        assert result["A"].beneficiary_entropy == 0.0


class TestTemporalRegularity:
    def test_regular_timing(self):
        accounts = [_acc("A")]
        txns = [_txn("A", "B", ts=f"2024-01-15T{10 + i}:00:00") for i in range(5)]
        result = compute_baselines(accounts, txns)
        assert result["A"].temporal_regularity > 0.5

    def test_irregular_timing(self):
        accounts = [_acc("A")]
        txns = [
            _txn("A", "B", ts="2024-01-15T10:00:00"),
            _txn("A", "B", ts="2024-01-15T10:05:00"),
            _txn("A", "B", ts="2024-01-15T18:30:00"),
        ]
        result = compute_baselines(accounts, txns)
        assert result["A"].temporal_regularity < 0.5


class TestDormancyBurst:
    def test_dormant_then_active(self):
        accounts = [_acc("D", age=200, avg_monthly=1)]
        txns = [_txn("D", f"R{i}") for i in range(12)]
        result = compute_baselines(accounts, txns)
        assert result["D"].dormancy_burst > 0.4

    def test_active_account(self):
        accounts = [_acc("A", age=30, avg_monthly=20)]
        txns = [_txn("A", "B") for _ in range(5)]
        result = compute_baselines(accounts, txns)
        assert result["A"].dormancy_burst == 0.0


class TestInboundOutboundAsymmetry:
    def test_mule_asymmetry(self):
        accounts = [_acc("M")]
        txns = [
            _txn("S1", "M", 50000),
            _txn("S2", "M", 50000),
            _txn("S3", "M", 50000),
            _txn("M", "D", 5000),
        ]
        result = compute_baselines(accounts, txns)
        assert result["M"].inbound_outbound_asymmetry > 0.3


class TestCompositeScore:
    def test_composite_bounded(self):
        accounts = [_acc("A", age=200, avg_monthly=1)]
        txns = [_txn("A", f"R{i}", 50000) for i in range(20)]
        in_txns = [_txn(f"S{i}", "A", 60000) for i in range(20)]
        result = compute_baselines(accounts, txns + in_txns)
        assert 0.0 <= result["A"].composite_score <= 1.0

    def test_no_txns_returns_zero(self):
        accounts = [_acc("EMPTY")]
        result = compute_baselines(accounts, [])
        assert result["EMPTY"].composite_score == 0.0
