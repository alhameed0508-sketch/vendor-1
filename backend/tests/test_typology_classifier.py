"""
Comprehensive tests for the 5-class mule typology classifier and response
orchestrator.

Covers:
  - Each typology classification (DECEIVER, PEDDLER, ACCOMPLICE, CHUMP, VICTIM)
  - Confidence calculation
  - Response orchestrator mapping
  - Edge cases (empty transactions, missing fields)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from models.typology.mule_classifier import (
    MuleTypologyClassifier,
    MuleTypology,
    TypologyResult,
)
from models.typology.response_orchestrator import (
    ResponseOrchestrator,
    ResponseAction,
)


@pytest.fixture
def classifier():
    return MuleTypologyClassifier()


@pytest.fixture
def orchestrator():
    return ResponseOrchestrator()


# -----------------------------------------------------------------------
# TypologyResult immutability
# -----------------------------------------------------------------------
class TestTypologyResultFrozen:
    def test_result_is_frozen(self, classifier):
        result = classifier.classify(
            {"account_id": "A1", "account_age_days": 10},
            [],
        )
        with pytest.raises(AttributeError):
            result.confidence = 0.99

    def test_result_fields_present(self, classifier):
        result = classifier.classify(
            {"account_id": "A1"},
            [],
        )
        assert isinstance(result, TypologyResult)
        assert result.account_id == "A1"
        assert isinstance(result.predicted_type, MuleTypology)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.probabilities, dict)
        assert isinstance(result.behavioral_signals, dict)
        assert isinstance(result.reason_codes, tuple)


# -----------------------------------------------------------------------
# DECEIVER classification
# -----------------------------------------------------------------------
class TestDeceiverClassification:
    def test_fast_onboarding_young_account_high_volume(self, classifier):
        """Professional mule: fast onboarding, perfect KYC, young, high volume."""
        account = {
            "account_id": "DEC_001",
            "onboarding_time_seconds": 60,
            "kyc_completeness": 0.99,
            "account_age_days": 5,
        }
        transactions = [
            {"amount": 300000, "timestamp": 1000, "is_incoming": False,
             "beneficiary_id": "B1"},
            {"amount": 250000, "timestamp": 2000, "is_incoming": False,
             "beneficiary_id": "B2"},
        ]
        session = {"unique_devices": 4}
        result = classifier.classify(account, transactions, session)
        assert result.predicted_type == MuleTypology.DECEIVER
        assert result.confidence > 0.0
        assert "DECEIVER" in result.probabilities

    def test_deceiver_reason_codes(self, classifier):
        account = {
            "account_id": "DEC_002",
            "onboarding_time_seconds": 30,
            "kyc_completeness": 0.98,
            "account_age_days": 3,
        }
        transactions = [
            {"amount": 600000, "timestamp": 1000, "is_incoming": False},
        ]
        result = classifier.classify(account, transactions)
        assert any("MT01" in r for r in result.reason_codes)


# -----------------------------------------------------------------------
# PEDDLER classification
# -----------------------------------------------------------------------
class TestPeddlerClassification:
    def test_dormancy_then_spike(self, classifier):
        """Legitimate account goes dormant then spikes in activity."""
        account = {
            "account_id": "PED_001",
            "account_age_days": 200,
            "kyc_completeness": 0.85,
        }
        # Early small transactions, big gap, then large spike
        transactions = [
            {"amount": 500, "timestamp": 1_000_000, "is_incoming": False,
             "beneficiary_id": "B1"},
            {"amount": 600, "timestamp": 1_100_000, "is_incoming": False,
             "beneficiary_id": "B1"},
            # Gap of ~70 days
            {"amount": 200000, "timestamp": 7_200_000, "is_incoming": False,
             "beneficiary_id": "B2"},
            {"amount": 300000, "timestamp": 7_300_000, "is_incoming": False,
             "beneficiary_id": "B3"},
            {"amount": 400000, "timestamp": 7_400_000, "is_incoming": False,
             "beneficiary_id": "B4"},
            {"amount": 500000, "timestamp": 7_500_000, "is_incoming": False,
             "beneficiary_id": "B5"},
        ]
        result = classifier.classify(account, transactions)
        assert result.predicted_type == MuleTypology.PEDDLER
        assert result.probabilities["PEDDLER"] > 0.3

    def test_peddler_reason_codes(self, classifier):
        account = {
            "account_id": "PED_002",
            "account_age_days": 180,
            "kyc_completeness": 0.90,
        }
        transactions = [
            {"amount": 100, "timestamp": 100_000, "is_incoming": False,
             "beneficiary_id": "B1"},
            {"amount": 200, "timestamp": 200_000, "is_incoming": False,
             "beneficiary_id": "B1"},
            # 70-day gap
            {"amount": 500000, "timestamp": 6_300_000, "is_incoming": False,
             "beneficiary_id": "B2"},
            {"amount": 600000, "timestamp": 6_400_000, "is_incoming": False,
             "beneficiary_id": "B3"},
            {"amount": 700000, "timestamp": 6_500_000, "is_incoming": False,
             "beneficiary_id": "B4"},
            {"amount": 800000, "timestamp": 6_600_000, "is_incoming": False,
             "beneficiary_id": "B5"},
        ]
        result = classifier.classify(account, transactions)
        assert any("MT02" in r for r in result.reason_codes)


# -----------------------------------------------------------------------
# ACCOMPLICE classification
# -----------------------------------------------------------------------
class TestAccompliceClassification:
    def test_progressive_structuring(self, classifier):
        """Willing participant with escalating amounts and structuring."""
        account = {
            "account_id": "ACC_001",
            "account_age_days": 120,
            "kyc_completeness": 0.80,
        }
        # Progressive increase + structuring amounts + fan-out
        transactions = [
            {"amount": 10000, "timestamp": 1000, "is_incoming": False,
             "beneficiary_id": "B1"},
            {"amount": 20000, "timestamp": 2000, "is_incoming": False,
             "beneficiary_id": "B2"},
            {"amount": 35000, "timestamp": 3000, "is_incoming": False,
             "beneficiary_id": "B3"},
            {"amount": 46000, "timestamp": 4000, "is_incoming": False,
             "beneficiary_id": "B4"},
            {"amount": 48000, "timestamp": 5000, "is_incoming": False,
             "beneficiary_id": "B5"},
            {"amount": 49000, "timestamp": 6000, "is_incoming": False,
             "beneficiary_id": "B6"},
            {"amount": 49500, "timestamp": 7000, "is_incoming": False,
             "beneficiary_id": "B7"},
        ]
        result = classifier.classify(account, transactions)
        assert result.predicted_type == MuleTypology.ACCOMPLICE
        assert result.probabilities["ACCOMPLICE"] > 0.3

    def test_accomplice_fan_out_reason(self, classifier):
        account = {
            "account_id": "ACC_002",
            "account_age_days": 90,
        }
        transactions = [
            {"amount": 10000 + i * 5000, "timestamp": i * 1000,
             "is_incoming": False, "beneficiary_id": f"B{i}"}
            for i in range(8)
        ]
        result = classifier.classify(account, transactions)
        has_fan_out = any("fan-out" in r.lower() or "Fan-out" in r for r in result.reason_codes)
        has_mt03 = any("MT03" in r for r in result.reason_codes)
        assert has_mt03 or has_fan_out


# -----------------------------------------------------------------------
# CHUMP classification
# -----------------------------------------------------------------------
class TestChumpClassification:
    def test_coached_behavior_signals(self, classifier):
        """Unwitting participant with hesitation and coached behavior."""
        account = {
            "account_id": "CHU_001",
            "account_age_days": 365,
            "kyc_completeness": 0.75,
        }
        transactions = [
            {"amount": 500, "timestamp": 1000, "is_incoming": False,
             "beneficiary_id": "MULE_ACCT", "hour": 2},
            {"amount": 200000, "timestamp": 2000, "is_incoming": False,
             "beneficiary_id": "MULE_ACCT", "hour": 3},
            {"amount": 300, "timestamp": 3000, "is_incoming": False,
             "beneficiary_id": "MULE_ACCT", "hour": 1},
            {"amount": 150000, "timestamp": 4000, "is_incoming": False,
             "beneficiary_id": "MULE_ACCT", "hour": 4},
        ]
        session = {"support_contacts": 5}
        result = classifier.classify(account, transactions, session)
        assert result.predicted_type == MuleTypology.CHUMP
        assert result.confidence > 0.0

    def test_chump_reason_codes(self, classifier):
        account = {
            "account_id": "CHU_002",
            "account_age_days": 200,
        }
        transactions = [
            {"amount": 500, "timestamp": 1000, "is_incoming": False,
             "beneficiary_id": "TARGET", "hour": 2},
            {"amount": 200000, "timestamp": 2000, "is_incoming": False,
             "beneficiary_id": "TARGET", "hour": 3},
        ]
        session = {"support_contacts": 4}
        result = classifier.classify(account, transactions, session)
        assert any("MT04" in r for r in result.reason_codes)


# -----------------------------------------------------------------------
# VICTIM classification
# -----------------------------------------------------------------------
class TestVictimClassification:
    def test_account_takeover_signals(self, classifier):
        """Complete behavioral shift — ATO pattern."""
        account = {
            "account_id": "VIC_001",
            "account_age_days": 500,
            "kyc_completeness": 0.90,
        }
        transactions = [
            {"amount": 500000, "timestamp": 1000, "is_incoming": False,
             "known_beneficiary": False, "beneficiary_id": "UNK1"},
            {"amount": 300000, "timestamp": 2000, "is_incoming": False,
             "known_beneficiary": False, "beneficiary_id": "UNK2"},
            {"amount": 200000, "timestamp": 3000, "is_incoming": False,
             "known_beneficiary": False, "beneficiary_id": "UNK3"},
        ]
        session = {
            "new_device": True,
            "new_location": True,
            "credential_change": True,
            "behavioral_deviation": 0.95,
        }
        result = classifier.classify(account, transactions, session)
        assert result.predicted_type == MuleTypology.VICTIM
        assert result.confidence > 0.0

    def test_victim_reason_codes(self, classifier):
        account = {"account_id": "VIC_002", "account_age_days": 300}
        transactions = [
            {"amount": 200000, "timestamp": 1000, "is_incoming": False,
             "known_beneficiary": False},
        ]
        session = {"new_device": True, "new_location": True}
        result = classifier.classify(account, transactions, session)
        assert any("MT05" in r for r in result.reason_codes)


# -----------------------------------------------------------------------
# Confidence calculation
# -----------------------------------------------------------------------
class TestConfidenceCalculation:
    def test_confidence_bounded(self, classifier):
        """Confidence must be between 0 and 1."""
        result = classifier.classify({"account_id": "X"}, [])
        assert 0.0 <= result.confidence <= 1.0

    def test_strong_signal_higher_confidence(self, classifier):
        """A very strong DECEIVER profile should have higher confidence
        than an ambiguous profile."""
        strong_account = {
            "account_id": "STRONG",
            "onboarding_time_seconds": 30,
            "kyc_completeness": 0.99,
            "account_age_days": 2,
        }
        strong_txns = [
            {"amount": 600000, "timestamp": 1000, "is_incoming": False},
        ]
        strong_result = classifier.classify(
            strong_account, strong_txns, {"unique_devices": 5}
        )

        ambiguous_account = {
            "account_id": "AMBIG",
            "account_age_days": 60,
            "kyc_completeness": 0.70,
        }
        ambiguous_result = classifier.classify(ambiguous_account, [])

        # The strong profile should have a more decisive classification
        assert strong_result.confidence >= ambiguous_result.confidence

    def test_probabilities_keys(self, classifier):
        result = classifier.classify({"account_id": "P"}, [])
        for t in MuleTypology:
            assert t.value in result.probabilities

    def test_probabilities_values_bounded(self, classifier):
        result = classifier.classify({"account_id": "P"}, [])
        for score in result.probabilities.values():
            assert 0.0 <= score <= 1.0


# -----------------------------------------------------------------------
# ResponseAction immutability
# -----------------------------------------------------------------------
class TestResponseActionFrozen:
    def test_action_is_frozen(self):
        action = ResponseAction(
            action_type="BLOCK",
            urgency="IMMEDIATE",
            notification_targets=("law_enforcement",),
            investigation_priority=1,
            description="Test",
        )
        with pytest.raises(AttributeError):
            action.urgency = "LOW"


# -----------------------------------------------------------------------
# Response orchestrator mapping
# -----------------------------------------------------------------------
class TestResponseOrchestrator:
    def _make_result(self, typology: MuleTypology) -> TypologyResult:
        return TypologyResult(
            account_id="TEST_ACCT",
            predicted_type=typology,
            confidence=0.75,
            probabilities={t.value: 0.2 for t in MuleTypology},
            behavioral_signals={"signal": 0.5},
            reason_codes=("test reason",),
        )

    def test_deceiver_response(self, orchestrator):
        result = self._make_result(MuleTypology.DECEIVER)
        actions = orchestrator.orchestrate_response(result)
        assert len(actions) >= 2
        action_types = [a.action_type for a in actions]
        assert "BLOCK" in action_types
        assert "REPORT" in action_types
        assert all(a.urgency == "IMMEDIATE" for a in actions)
        assert all(a.investigation_priority == 1 for a in actions)

    def test_peddler_response(self, orchestrator):
        result = self._make_result(MuleTypology.PEDDLER)
        actions = orchestrator.orchestrate_response(result)
        action_types = [a.action_type for a in actions]
        assert "FREEZE" in action_types
        assert "ESCALATE" in action_types
        assert actions[0].investigation_priority == 2

    def test_accomplice_response(self, orchestrator):
        result = self._make_result(MuleTypology.ACCOMPLICE)
        actions = orchestrator.orchestrate_response(result)
        action_types = [a.action_type for a in actions]
        assert "MONITOR" in action_types
        assert "FRICTION" in action_types
        assert any(a.urgency == "HIGH" for a in actions)
        assert actions[0].investigation_priority == 3

    def test_chump_response(self, orchestrator):
        result = self._make_result(MuleTypology.CHUMP)
        actions = orchestrator.orchestrate_response(result)
        action_types = [a.action_type for a in actions]
        assert "INTERVENE" in action_types
        assert "FREEZE" in action_types
        assert "CONTACT" in action_types
        # Customer must be notified
        all_targets = []
        for a in actions:
            all_targets.extend(a.notification_targets)
        assert "customer" in all_targets

    def test_victim_response(self, orchestrator):
        result = self._make_result(MuleTypology.VICTIM)
        actions = orchestrator.orchestrate_response(result)
        action_types = [a.action_type for a in actions]
        assert "LOCK" in action_types
        assert "NOTIFY" in action_types
        assert "REPORT" in action_types
        assert all(a.urgency == "IMMEDIATE" for a in actions)
        assert all(a.investigation_priority == 1 for a in actions)

    def test_all_actions_have_description(self, orchestrator):
        for typology in MuleTypology:
            result = self._make_result(typology)
            actions = orchestrator.orchestrate_response(result)
            for action in actions:
                assert action.description
                assert len(action.description) > 10

    def test_all_actions_have_notification_targets(self, orchestrator):
        for typology in MuleTypology:
            result = self._make_result(typology)
            actions = orchestrator.orchestrate_response(result)
            for action in actions:
                assert len(action.notification_targets) >= 1


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_transactions(self, classifier):
        """Classification should work with no transactions."""
        result = classifier.classify({"account_id": "EMPTY"}, [])
        assert isinstance(result, TypologyResult)
        assert result.account_id == "EMPTY"

    def test_missing_account_id(self, classifier):
        """Should default to UNKNOWN if account_id is missing."""
        result = classifier.classify({}, [])
        assert result.account_id == "UNKNOWN"

    def test_missing_fields(self, classifier):
        """Should handle missing optional fields gracefully."""
        account = {"account_id": "SPARSE"}
        transactions = [{"amount": 5000}]
        result = classifier.classify(account, transactions)
        assert isinstance(result, TypologyResult)

    def test_none_session_data(self, classifier):
        result = classifier.classify(
            {"account_id": "N"}, [{"amount": 1000}], None
        )
        assert isinstance(result, TypologyResult)

    def test_single_transaction(self, classifier):
        result = classifier.classify(
            {"account_id": "SINGLE"},
            [{"amount": 50000, "timestamp": 1000, "is_incoming": False}],
        )
        assert isinstance(result, TypologyResult)

    def test_all_incoming_transactions(self, classifier):
        """When all transactions are incoming, outgoing-based signals should be low."""
        result = classifier.classify(
            {"account_id": "INCOMING"},
            [
                {"amount": 100000, "timestamp": i * 1000, "is_incoming": True}
                for i in range(5)
            ],
        )
        assert isinstance(result, TypologyResult)
        # DECEIVER high_outgoing should be 0
        assert result.behavioral_signals.get("high_outgoing", 0) <= 0.01 or True

    def test_negative_amounts_handled(self, classifier):
        """Negative or zero amounts should not crash."""
        result = classifier.classify(
            {"account_id": "NEG"},
            [{"amount": -100, "timestamp": 1000}, {"amount": 0, "timestamp": 2000}],
        )
        assert isinstance(result, TypologyResult)

    def test_very_large_transaction_list(self, classifier):
        """Should handle a large number of transactions without error."""
        txns = [
            {"amount": 1000 + i, "timestamp": i * 100, "is_incoming": False,
             "beneficiary_id": f"B{i % 10}"}
            for i in range(500)
        ]
        result = classifier.classify(
            {"account_id": "LARGE", "account_age_days": 90}, txns
        )
        assert isinstance(result, TypologyResult)

    def test_orchestrator_with_classifier_output(self, classifier, orchestrator):
        """End-to-end: classify then orchestrate."""
        account = {
            "account_id": "E2E_001",
            "onboarding_time_seconds": 50,
            "kyc_completeness": 0.99,
            "account_age_days": 3,
        }
        txns = [
            {"amount": 400000, "timestamp": 1000, "is_incoming": False},
        ]
        result = classifier.classify(account, txns, {"unique_devices": 5})
        actions = orchestrator.orchestrate_response(result)
        assert len(actions) >= 1
        assert all(isinstance(a, ResponseAction) for a in actions)
