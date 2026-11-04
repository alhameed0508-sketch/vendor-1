"""
Tests for Markov State Transition Scorer (MK01-MK05).
=====================================================
Verifies state classification, transition matrix computation,
canonical mule lifecycle scoring, reason code generation,
batch scoring, and edge cases.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timedelta

import pytest

from models.temporal.markov_state import (
    AccountState,
    MarkovStateResult,
    MarkovStateScorer,
    MarkovTransitionMatrix,
    _count_dormant_sweep_cycles,
    _extract_timestamps,
    _parse_timestamp,
    _zero_result,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _acc(acc_id: str, age: int = 30, avg_monthly: int = 8) -> dict:
    """Build a minimal account metadata dict."""
    return {
        "account_id": acc_id,
        "account_age_days": age,
        "avg_monthly_txn": avg_monthly,
    }


def _txn(
    from_acc: str,
    to_acc: str,
    amount: float = 10_000.0,
    ts: str = "2024-06-15T10:00:00",
) -> dict:
    """Build a minimal transaction dict."""
    return {
        "from_account": from_acc,
        "to_account": to_acc,
        "amount": amount,
        "timestamp": ts,
    }


def _week_ts(base: datetime, week_offset: int, day: int = 0, hour: int = 10) -> str:
    """Return an ISO timestamp offset by ``week_offset`` weeks from ``base``."""
    dt = base + timedelta(weeks=week_offset, days=day, hours=hour)
    return dt.isoformat()


BASE_DATE = datetime(2024, 1, 1, 0, 0, 0)


@pytest.fixture
def scorer() -> MarkovStateScorer:
    return MarkovStateScorer()


# ---------------------------------------------------------------------------
# AccountState enum
# ---------------------------------------------------------------------------


class TestAccountState:
    def test_has_five_states(self):
        assert len(AccountState) == 5

    def test_values(self):
        expected = {"DORMANT", "LOW_ACTIVITY", "RECEIVING", "FORWARDING", "SWEEP"}
        assert {s.value for s in AccountState} == expected


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


class TestFrozenDataclasses:
    def test_markov_state_result_is_frozen(self):
        result = _zero_result("A")
        with pytest.raises(AttributeError):
            result.transition_score = 0.99  # type: ignore[misc]

    def test_markov_transition_matrix_is_frozen(self):
        matrix = MarkovTransitionMatrix(probabilities=(), state_counts=())
        with pytest.raises(AttributeError):
            matrix.probabilities = ()  # type: ignore[misc]

    def test_transition_matrix_get_probability(self):
        matrix = MarkovTransitionMatrix(
            probabilities=(("DORMANT", "RECEIVING", 0.5),),
            state_counts=(("DORMANT", 4),),
        )
        assert matrix.get_probability("DORMANT", "RECEIVING") == 0.5
        assert matrix.get_probability("DORMANT", "SWEEP") == 0.0


# ---------------------------------------------------------------------------
# State classification
# ---------------------------------------------------------------------------


class TestStateClassification:
    """Verify _classify_state for each AccountState."""

    def test_dormant_no_transactions(self, scorer):
        state = scorer._classify_state(
            _acc("A"),
            [],
            [],
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.DORMANT

    def test_dormant_single_transaction(self, scorer):
        txns = [_txn("A", "B", ts=_week_ts(BASE_DATE, 0, day=1))]
        state = scorer._classify_state(
            _acc("A"),
            txns,
            [],
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.DORMANT

    def test_low_activity_balanced(self, scorer):
        """2-5 transactions with balanced in/out -> LOW_ACTIVITY."""
        out_txns = [
            _txn("A", "B", 5000, _week_ts(BASE_DATE, 0, day=1)),
            _txn("A", "C", 5000, _week_ts(BASE_DATE, 0, day=2)),
        ]
        in_txns = [
            _txn("X", "A", 5000, _week_ts(BASE_DATE, 0, day=1)),
        ]
        state = scorer._classify_state(
            _acc("A"),
            out_txns,
            in_txns,
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.LOW_ACTIVITY

    def test_receiving_state(self, scorer):
        """Incoming > outgoing * 2 -> RECEIVING."""
        in_txns = [
            _txn("S1", "A", 50_000, _week_ts(BASE_DATE, 0, day=1)),
            _txn("S2", "A", 50_000, _week_ts(BASE_DATE, 0, day=2)),
            _txn("S3", "A", 50_000, _week_ts(BASE_DATE, 0, day=3)),
        ]
        out_txns = [
            _txn("A", "D", 5_000, _week_ts(BASE_DATE, 0, day=4)),
        ]
        state = scorer._classify_state(
            _acc("A"),
            out_txns,
            in_txns,
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.RECEIVING

    def test_forwarding_state(self, scorer):
        """Outgoing > incoming * 0.5 AND pass-through ratio > 0.7 -> FORWARDING."""
        in_txns = [
            _txn("S1", "A", 100_000, _week_ts(BASE_DATE, 0, day=1)),
        ]
        out_txns = [
            _txn("A", "D1", 40_000, _week_ts(BASE_DATE, 0, day=2)),
            _txn("A", "D2", 40_000, _week_ts(BASE_DATE, 0, day=3)),
        ]
        state = scorer._classify_state(
            _acc("A"),
            out_txns,
            in_txns,
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.FORWARDING

    def test_sweep_state(self, scorer):
        """Outgoing/incoming > 0.9 AND balance near zero -> SWEEP."""
        in_txns = [
            _txn("S1", "A", 100_000, _week_ts(BASE_DATE, 0, day=1)),
        ]
        out_txns = [
            _txn("A", "D1", 50_000, _week_ts(BASE_DATE, 0, day=2)),
            _txn("A", "D2", 48_000, _week_ts(BASE_DATE, 0, day=3)),
        ]
        state = scorer._classify_state(
            _acc("A"),
            out_txns,
            in_txns,
            BASE_DATE,
            BASE_DATE + timedelta(weeks=1),
        )
        assert state == AccountState.SWEEP


# ---------------------------------------------------------------------------
# Transition matrix
# ---------------------------------------------------------------------------


class TestTransitionMatrix:
    def test_simple_sequence(self, scorer):
        history = ["DORMANT", "RECEIVING", "FORWARDING", "SWEEP"]
        matrix = scorer._compute_transition_matrix(history)

        assert matrix.get_probability("DORMANT", "RECEIVING") == 1.0
        assert matrix.get_probability("RECEIVING", "FORWARDING") == 1.0
        assert matrix.get_probability("FORWARDING", "SWEEP") == 1.0

    def test_repeated_state(self, scorer):
        history = ["DORMANT", "DORMANT", "DORMANT", "RECEIVING"]
        matrix = scorer._compute_transition_matrix(history)

        # 2 out of 3 transitions from DORMANT stay DORMANT
        p_self = matrix.get_probability("DORMANT", "DORMANT")
        p_recv = matrix.get_probability("DORMANT", "RECEIVING")
        assert abs(p_self - 2 / 3) < 0.01
        assert abs(p_recv - 1 / 3) < 0.01

    def test_empty_history(self, scorer):
        matrix = scorer._compute_transition_matrix([])
        assert matrix.probabilities == ()

    def test_single_state(self, scorer):
        matrix = scorer._compute_transition_matrix(["DORMANT"])
        assert matrix.probabilities == ()
        # State count should reflect the single observation
        counts = dict(matrix.state_counts)
        assert counts.get("DORMANT", 0) == 1

    def test_probabilities_sum_to_one(self, scorer):
        history = [
            "DORMANT",
            "RECEIVING",
            "FORWARDING",
            "SWEEP",
            "DORMANT",
            "RECEIVING",
        ]
        matrix = scorer._compute_transition_matrix(history)

        # For each from_state that has outgoing transitions, probs should sum to 1
        from_states_seen = {f for f, _, _ in matrix.probabilities}
        for from_s in from_states_seen:
            total = sum(p for f, _, p in matrix.probabilities if f == from_s)
            assert abs(total - 1.0) < 0.01, f"Probs from {from_s} sum to {total}"


# ---------------------------------------------------------------------------
# Mule lifecycle scoring
# ---------------------------------------------------------------------------


class TestMuleLifecycleScoring:
    def test_canonical_lifecycle_scores_high(self, scorer):
        """The textbook mule lifecycle should get a high score."""
        history = ["DORMANT", "RECEIVING", "FORWARDING", "SWEEP"]
        matrix = scorer._compute_transition_matrix(history)
        score = scorer._score_mule_lifecycle(matrix)
        assert score > 0.5

    def test_normal_behavior_scores_low(self, scorer):
        """Stable low-activity account should score near zero."""
        history = ["LOW_ACTIVITY"] * 20
        matrix = scorer._compute_transition_matrix(history)
        score = scorer._score_mule_lifecycle(matrix)
        assert score == 0.0

    def test_partial_lifecycle(self, scorer):
        """Only some mule transitions present -> partial score."""
        history = ["DORMANT", "RECEIVING", "RECEIVING", "LOW_ACTIVITY"]
        matrix = scorer._compute_transition_matrix(history)
        score = scorer._score_mule_lifecycle(matrix)
        # Only DORMANT->RECEIVING fires, so score should be moderate
        assert 0.0 < score < 0.6

    def test_score_bounded_zero_one(self, scorer):
        """Score should always be in [0, 1]."""
        for history in [
            ["DORMANT", "RECEIVING", "FORWARDING", "SWEEP"],
            ["LOW_ACTIVITY"] * 10,
            ["SWEEP", "DORMANT"],
            [],
        ]:
            if len(history) < 2:
                continue
            matrix = scorer._compute_transition_matrix(history)
            score = scorer._score_mule_lifecycle(matrix)
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for {history}"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


class TestReasonCodes:
    def test_mk01_dormant_to_receiving(self, scorer):
        history = ["DORMANT", "RECEIVING"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert any("MK01" in c for c in codes)

    def test_mk02_receiving_to_forwarding(self, scorer):
        history = ["RECEIVING", "FORWARDING"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert any("MK02" in c for c in codes)

    def test_mk03_forwarding_to_sweep(self, scorer):
        history = ["FORWARDING", "SWEEP"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert any("MK03" in c for c in codes)

    def test_mk04_rapid_lifecycle(self, scorer):
        """DORMANT -> SWEEP in < 4 weeks -> MK04."""
        history = ["DORMANT", "RECEIVING", "SWEEP"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert any("MK04" in c for c in codes)

    def test_mk04_not_triggered_if_slow(self, scorer):
        """DORMANT -> ... -> SWEEP over many weeks should NOT fire MK04."""
        history = ["DORMANT"] + ["LOW_ACTIVITY"] * 5 + ["RECEIVING"] + ["SWEEP"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert not any("MK04" in c for c in codes)

    def test_mk05_cyclic_pattern(self, scorer):
        """Repeated DORMANT->SWEEP cycles -> MK05."""
        history = [
            "DORMANT",
            "RECEIVING",
            "SWEEP",
            "DORMANT",
            "FORWARDING",
            "SWEEP",
        ]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert any("MK05" in c for c in codes)

    def test_mk05_not_triggered_single_cycle(self, scorer):
        """Single cycle should NOT trigger MK05."""
        history = ["DORMANT", "RECEIVING", "SWEEP"]
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert not any("MK05" in c for c in codes)

    def test_no_reason_codes_for_normal_account(self, scorer):
        """A purely low-activity history should produce zero reason codes."""
        history = ["LOW_ACTIVITY"] * 10
        matrix = scorer._compute_transition_matrix(history)
        codes = scorer._generate_reason_codes(matrix, history)
        assert len(codes) == 0


# ---------------------------------------------------------------------------
# End-to-end score_account
# ---------------------------------------------------------------------------


class TestScoreAccount:
    def test_canonical_mule_gets_high_score(self, scorer):
        """Simulate a textbook mule lifecycle across weekly windows."""
        acc = _acc("MULE_001")

        # Week 0-3: dormant (no transactions)
        # Week 4-7: receiving (heavy inflow, no outflow)
        # Week 8-11: forwarding (outflow ~ 80% of inflow)
        # Week 12-14: sweep (outflow ~ 98% of inflow)

        out_txns = []
        in_txns = []

        # Weeks 4-7: receiving phase
        for w in range(4, 8):
            for d in range(3):
                in_txns.append(_txn("S1", "MULE_001", 80_000, _week_ts(BASE_DATE, w, day=d)))

        # Weeks 8-11: forwarding phase
        for w in range(8, 12):
            in_txns.append(_txn("S1", "MULE_001", 100_000, _week_ts(BASE_DATE, w, day=0)))
            out_txns.append(_txn("MULE_001", "D1", 40_000, _week_ts(BASE_DATE, w, day=1)))
            out_txns.append(_txn("MULE_001", "D2", 40_000, _week_ts(BASE_DATE, w, day=2)))

        # Weeks 12-14: sweep phase
        for w in range(12, 15):
            in_txns.append(_txn("S1", "MULE_001", 100_000, _week_ts(BASE_DATE, w, day=0)))
            out_txns.append(_txn("MULE_001", "D1", 50_000, _week_ts(BASE_DATE, w, day=1)))
            out_txns.append(_txn("MULE_001", "D2", 48_000, _week_ts(BASE_DATE, w, day=2)))

        result = scorer.score_account("MULE_001", acc, out_txns, in_txns, window_weeks=24)

        assert isinstance(result, MarkovStateResult)
        assert result.account_id == "MULE_001"
        assert result.transition_score > 0.3
        assert result.mule_lifecycle_probability > 0.0
        assert len(result.state_history) > 0
        assert len(result.reason_codes) > 0

    def test_normal_account_gets_low_score(self, scorer):
        """A stable low-activity account should score near zero."""
        acc = _acc("NORMAL_001", age=365, avg_monthly=5)

        out_txns = []
        in_txns = []

        # Steady low activity for 20 weeks
        for w in range(20):
            out_txns.append(_txn("NORMAL_001", "SHOP", 2_000, _week_ts(BASE_DATE, w, day=3)))
            in_txns.append(_txn("SALARY", "NORMAL_001", 2_500, _week_ts(BASE_DATE, w, day=0)))

        result = scorer.score_account("NORMAL_001", acc, out_txns, in_txns, window_weeks=24)

        assert result.transition_score < 0.3
        # Should have no mule-specific reason codes
        mule_codes = [c for c in result.reason_codes if c.startswith("MK")]
        assert len(mule_codes) == 0

    def test_result_fields_populated(self, scorer):
        """Verify all fields of the result are populated correctly."""
        acc = _acc("A")
        out_txns = [_txn("A", "B", 10_000, _week_ts(BASE_DATE, 0, day=1))]
        in_txns = [
            _txn("S", "A", 50_000, _week_ts(BASE_DATE, 0, day=0)),
            _txn("S", "A", 50_000, _week_ts(BASE_DATE, 1, day=0)),
        ]
        result = scorer.score_account("A", acc, out_txns, in_txns, window_weeks=24)

        assert result.account_id == "A"
        assert isinstance(result.current_state, str)
        assert isinstance(result.state_history, tuple)
        assert isinstance(result.reason_codes, tuple)
        assert 0.0 <= result.transition_score <= 1.0
        assert 0.0 <= result.mule_lifecycle_probability <= 1.0

    def test_transition_score_bounded(self, scorer):
        """Score must always be in [0, 1] regardless of input."""
        acc = _acc("A")
        # Create an extreme scenario
        in_txns = [_txn("S", "A", 1_000_000, _week_ts(BASE_DATE, w)) for w in range(20)]
        out_txns = [_txn("A", "D", 999_000, _week_ts(BASE_DATE, w, day=3)) for w in range(20)]
        result = scorer.score_account("A", acc, out_txns, in_txns, window_weeks=24)
        assert 0.0 <= result.transition_score <= 1.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_transactions(self, scorer):
        """No transactions should return a zero-score result."""
        result = scorer.score_account("EMPTY", _acc("EMPTY"), [], [])
        assert result.transition_score == 0.0
        assert result.mule_lifecycle_probability == 0.0
        assert result.state_history == ()
        assert result.reason_codes == ()
        assert result.current_state == AccountState.DORMANT.value

    def test_single_transaction(self, scorer):
        """A single transaction is insufficient for transitions."""
        acc = _acc("ONE")
        out_txns = [_txn("ONE", "B", 5_000, "2024-06-15T10:00:00")]
        result = scorer.score_account("ONE", acc, out_txns, [])
        assert result.transition_score == 0.0
        assert result.mule_lifecycle_probability == 0.0

    def test_very_short_history(self, scorer):
        """Two transactions in the same week -> single window."""
        acc = _acc("SHORT")
        out_txns = [
            _txn("SHORT", "B", 5_000, "2024-06-15T10:00:00"),
            _txn("SHORT", "C", 5_000, "2024-06-15T14:00:00"),
        ]
        result = scorer.score_account("SHORT", acc, out_txns, [])
        # Only 1 window -> no transitions possible
        assert result.transition_score == 0.0

    def test_missing_timestamps(self, scorer):
        """Transactions without timestamp field should be handled gracefully."""
        acc = _acc("BAD")
        txns = [
            {"from_account": "BAD", "to_account": "B", "amount": 5000},
            {"from_account": "BAD", "to_account": "C", "amount": 5000},
        ]
        result = scorer.score_account("BAD", acc, txns, [])
        assert result.transition_score == 0.0
        assert result.current_state == AccountState.DORMANT.value

    def test_invalid_timestamps(self, scorer):
        """Malformed timestamps should be handled gracefully."""
        acc = _acc("INVALID")
        txns = [
            _txn("INVALID", "B", 5000, "not-a-date"),
            _txn("INVALID", "C", 5000, "also-not-a-date"),
        ]
        result = scorer.score_account("INVALID", acc, txns, [])
        assert result.transition_score == 0.0

    def test_datetime_objects_as_timestamps(self, scorer):
        """Timestamps that are already datetime objects should work."""
        acc = _acc("DT")
        dt1 = datetime(2024, 6, 1, 10, 0, 0)
        dt2 = datetime(2024, 6, 8, 10, 0, 0)
        dt3 = datetime(2024, 6, 15, 10, 0, 0)
        out_txns = [
            {"from_account": "DT", "to_account": "B", "amount": 5000, "timestamp": dt1},
            {"from_account": "DT", "to_account": "C", "amount": 5000, "timestamp": dt2},
        ]
        in_txns = [
            {
                "from_account": "S",
                "to_account": "DT",
                "amount": 50000,
                "timestamp": dt3,
            },
        ]
        result = scorer.score_account("DT", acc, out_txns, in_txns)
        # Should not raise, and should produce some result
        assert result.account_id == "DT"
        assert len(result.state_history) >= 1


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------


class TestBatchScoring:
    def test_batch_returns_all_accounts(self, scorer):
        accounts = [_acc("A"), _acc("B"), _acc("C")]
        txns = [
            _txn("A", "B", 10_000, "2024-06-01T10:00:00"),
            _txn("A", "C", 10_000, "2024-06-08T10:00:00"),
            _txn("B", "C", 5_000, "2024-06-01T12:00:00"),
        ]
        results = scorer.score_batch(accounts, txns)
        assert set(results.keys()) == {"A", "B", "C"}
        for acc_id, result in results.items():
            assert isinstance(result, MarkovStateResult)
            assert result.account_id == acc_id

    def test_batch_empty_inputs(self, scorer):
        results = scorer.score_batch([], [])
        assert results == {}

    def test_batch_no_transactions(self, scorer):
        accounts = [_acc("X"), _acc("Y")]
        results = scorer.score_batch(accounts, [])
        assert len(results) == 2
        for result in results.values():
            assert result.transition_score == 0.0

    def test_batch_mule_vs_normal(self, scorer):
        """In a batch, a mule-like account should score higher than a normal one."""
        accounts = [_acc("MULE"), _acc("NORMAL")]

        txns = []
        # MULE: dormant then receiving then forwarding then sweep
        for w in range(4, 8):
            for d in range(3):
                txns.append(_txn("S", "MULE", 80_000, _week_ts(BASE_DATE, w, day=d)))
        for w in range(8, 12):
            txns.append(_txn("S", "MULE", 100_000, _week_ts(BASE_DATE, w, day=0)))
            txns.append(_txn("MULE", "D", 40_000, _week_ts(BASE_DATE, w, day=1)))
            txns.append(_txn("MULE", "D2", 40_000, _week_ts(BASE_DATE, w, day=2)))
        for w in range(12, 15):
            txns.append(_txn("S", "MULE", 100_000, _week_ts(BASE_DATE, w, day=0)))
            txns.append(_txn("MULE", "D", 50_000, _week_ts(BASE_DATE, w, day=1)))
            txns.append(_txn("MULE", "D2", 48_000, _week_ts(BASE_DATE, w, day=2)))

        # NORMAL: steady low activity
        for w in range(20):
            txns.append(_txn("NORMAL", "SHOP", 2_000, _week_ts(BASE_DATE, w, day=3)))
            txns.append(_txn("SALARY", "NORMAL", 2_500, _week_ts(BASE_DATE, w, day=0)))

        results = scorer.score_batch(accounts, txns)
        assert results["MULE"].transition_score > results["NORMAL"].transition_score


# ---------------------------------------------------------------------------
# Private helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_parse_timestamp_iso(self):
        dt = _parse_timestamp("2024-06-15T10:00:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6

    def test_parse_timestamp_with_z(self):
        dt = _parse_timestamp("2024-06-15T10:00:00Z")
        assert dt is not None

    def test_parse_timestamp_invalid(self):
        assert _parse_timestamp("not-a-date") is None
        assert _parse_timestamp(12345) is None
        assert _parse_timestamp(None) is None

    def test_parse_timestamp_datetime_passthrough(self):
        original = datetime(2024, 6, 15, 10, 0, 0)
        assert _parse_timestamp(original) is original

    def test_extract_timestamps_mixed(self):
        txns = [
            {"timestamp": "2024-06-15T10:00:00"},
            {"timestamp": "invalid"},
            {"amount": 100},  # no timestamp key
        ]
        result = _extract_timestamps(txns)
        assert len(result) == 1

    def test_count_dormant_sweep_cycles_none(self):
        assert _count_dormant_sweep_cycles([]) == 0
        assert _count_dormant_sweep_cycles(["DORMANT"]) == 0
        assert _count_dormant_sweep_cycles(["SWEEP"]) == 0

    def test_count_dormant_sweep_cycles_one(self):
        assert _count_dormant_sweep_cycles(["DORMANT", "SWEEP"]) == 1

    def test_count_dormant_sweep_cycles_two(self):
        history = ["DORMANT", "RECEIVING", "SWEEP", "DORMANT", "FORWARDING", "SWEEP"]
        assert _count_dormant_sweep_cycles(history) == 2

    def test_count_dormant_sweep_cycles_incomplete(self):
        history = ["DORMANT", "RECEIVING", "SWEEP", "DORMANT", "RECEIVING"]
        assert _count_dormant_sweep_cycles(history) == 1

    def test_zero_result(self):
        result = _zero_result("TEST")
        assert result.account_id == "TEST"
        assert result.transition_score == 0.0
        assert result.mule_lifecycle_probability == 0.0
        assert result.state_history == ()
        assert result.reason_codes == ()
        assert result.current_state == AccountState.DORMANT.value
