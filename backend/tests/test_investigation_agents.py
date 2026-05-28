"""
Tests for Phase 9 — Agentic AI Investigation.

Covers:
- CaseAssemblyAgent: case assembly, evidence classification, case strength
- NarrativeAgent: STR narrative generation, validation, template fallback
- AlertPriorityScorer: single alert scoring, queue sorting, SAR likelihood
- GenAI copilot: investigate_query, suggest_next_steps, generate_summary
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from services.investigation.case_assembler import (
    CaseAssemblyAgent,
    CaseFile,
    EvidenceItem,
)
from services.investigation.narrative_agent import NarrativeAgent, STRNarrative
from models.investigation.priority_scorer import AlertPriorityScorer, AlertPriorityResult
from services.genai_service import GenAIService, ChatResponse


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def full_alert_data():
    """Rich alert data with nodes, edges, reason codes, shared devices."""
    return {
        "alert_id": "ALT_INV_001",
        "severity": "CRITICAL",
        "risk_score": 0.92,
        "confidence": 0.88,
        "total_amount": 2_500_000.0,
        "txn_count": 55,
        "account_count": 6,
        "gnn_score": 0.81,
        "cluster_id": "CL_100",
        "shared_devices": ["DEV_A1", "DEV_A2", "DEV_A3"],
        "shared_ips": ["10.0.0.1", "10.0.0.2"],
        "reason_codes": [
            "R01: Account age < 7 days",
            "R04: Amounts structured below 50k threshold",
            "R06: Same-day credit-debit (pass-through)",
            "R09: Rapid fund consolidation",
            "R12: Device shared across 3+ accounts",
        ],
        "nodes": [
            {
                "account_id": "AC20000001",
                "role": "SOURCE",
                "smurf_score": 0.95,
                "bank": "IOB",
                "city": "Chennai",
                "account_age_days": 2,
                "kyc_status": "PENDING",
                "betweenness_centrality": 0.45,
            },
            {
                "account_id": "AC20000002",
                "role": "MULE",
                "smurf_score": 0.80,
                "bank": "SBI",
                "city": "Mumbai",
                "account_age_days": 4,
                "kyc_status": "PENDING",
                "betweenness_centrality": 0.60,
            },
            {
                "account_id": "AC20000003",
                "role": "AGGREGATOR",
                "smurf_score": 0.72,
                "bank": "HDFC",
                "city": "Delhi",
                "account_age_days": 1,
                "kyc_status": "VERIFIED",
                "betweenness_centrality": 0.10,
            },
        ],
        "edges": [
            {
                "from_account": "AC20000001",
                "to_account": "AC20000002",
                "total_amount": 900_000.0,
                "txn_count": 25,
                "pattern": "SMURFING",
            },
            {
                "from_account": "AC20000002",
                "to_account": "AC20000003",
                "total_amount": 850_000.0,
                "txn_count": 18,
                "pattern": "CONSOLIDATION",
            },
        ],
    }


@pytest.fixture
def minimal_alert_data():
    """Minimal alert data with only required fields."""
    return {
        "alert_id": "ALT_INV_002",
        "severity": "MEDIUM",
        "risk_score": 0.35,
        "total_amount": 50_000.0,
        "txn_count": 3,
        "reason_codes": ["R01: Account age < 7 days"],
        "nodes": [],
        "edges": [],
        "shared_devices": [],
        "shared_ips": [],
    }


@pytest.fixture
def sample_transactions():
    """Sample transaction list for case assembly."""
    return [
        {
            "from_account": "AC20000001",
            "to_account": "AC20000002",
            "amount": 45000,
            "date": "2025-05-01",
            "pattern": "SMURFING",
        },
        {
            "from_account": "AC20000001",
            "to_account": "AC20000002",
            "amount": 48000,
            "date": "2025-05-02",
            "pattern": "SMURFING",
        },
        {
            "from_account": "AC20000002",
            "to_account": "AC20000003",
            "amount": 90000,
            "date": "2025-05-03",
            "pattern": "CONSOLIDATION",
        },
    ]


@pytest.fixture
def sample_accounts():
    """Sample account list for case assembly."""
    return [
        {"account_id": "AC20000001", "role": "SOURCE"},
        {"account_id": "AC20000002", "role": "MULE"},
        {"account_id": "AC20000004", "role": "BENEFICIARY"},
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CaseAssemblyAgent Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCaseAssemblyFull:
    """Test case assembly with rich alert data."""

    def test_assemble_returns_case_file(self, full_alert_data, sample_transactions, sample_accounts):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
            transactions=sample_transactions,
            accounts=sample_accounts,
        )
        assert isinstance(case, CaseFile)
        assert case.alert_id == "ALT_INV_001"

    def test_account_ids_from_nodes_and_accounts(self, full_alert_data, sample_transactions, sample_accounts):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
            transactions=sample_transactions,
            accounts=sample_accounts,
        )
        # Should have node IDs + extra from accounts (AC20000004)
        assert "AC20000001" in case.account_ids
        assert "AC20000002" in case.account_ids
        assert "AC20000003" in case.account_ids
        assert "AC20000004" in case.account_ids
        assert len(case.account_ids) == 4

    def test_transaction_summary(self, full_alert_data, sample_transactions):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
            transactions=sample_transactions,
        )
        assert case.transaction_summary["total_amount"] == 2_500_000.0
        assert len(case.transaction_summary["top_counterparties"]) > 0
        assert case.transaction_summary["date_range"]["from"] == "2025-05-01"
        assert case.transaction_summary["date_range"]["to"] == "2025-05-03"

    def test_graph_context(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.graph_context["shared_device_count"] == 3
        assert case.graph_context["shared_ip_count"] == 2
        assert case.graph_context["node_count"] == 3
        assert case.graph_context["edge_count"] == 2
        assert case.graph_context["cluster_id"] == "CL_100"

    def test_behavioral_profile(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.behavioral_profile["deviation_count"] == 3
        assert case.behavioral_profile["gnn_score"] == 0.81

    def test_screening_results(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.screening_results["total_reason_codes"] == 5
        assert len(case.screening_results["rule_triggers"]) == 5

    def test_typology_extraction(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.typology is not None
        assert "SMURFING" in case.typology["patterns"]
        assert "CONSOLIDATION" in case.typology["patterns"]

    def test_timeline_includes_events(self, full_alert_data, sample_transactions):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
            transactions=sample_transactions,
        )
        assert len(case.timeline) > 0
        event_types = [e["event_type"] for e in case.timeline]
        assert "account_created" in event_types
        assert "transaction" in event_types
        assert "alert_generated" in event_types

    def test_case_file_immutability(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        with pytest.raises(AttributeError):
            case.alert_id = "MODIFIED"

    def test_created_at_populated(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.created_at is not None
        assert len(case.created_at) > 0


class TestCaseAssemblyMinimal:
    """Test case assembly with minimal data."""

    def test_assemble_with_minimal_data(self, minimal_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_002",
            alert_data=minimal_alert_data,
        )
        assert isinstance(case, CaseFile)
        assert case.alert_id == "ALT_INV_002"
        assert len(case.account_ids) == 0
        assert case.typology is None

    def test_no_evidence_gives_weak_case(self, minimal_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_002",
            alert_data=minimal_alert_data,
        )
        # Only transaction evidence (50k => LOW severity) => WEAK
        assert case.case_strength == "WEAK"


class TestEvidenceClassification:
    """Test evidence item classification logic."""

    def test_high_amount_gets_high_severity(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        txn_evidence = [
            e for e in case.evidence_items if e.evidence_type == "transaction"
        ]
        assert len(txn_evidence) == 1
        assert txn_evidence[0].severity == "HIGH"

    def test_shared_devices_high_severity(self, full_alert_data):
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        device_evidence = [
            e for e in case.evidence_items if e.evidence_type == "device"
        ]
        assert len(device_evidence) == 1
        assert device_evidence[0].severity == "HIGH"

    def test_evidence_item_immutability(self):
        item = EvidenceItem(
            evidence_type="test",
            description="test description",
            data={"key": "value"},
            severity="HIGH",
        )
        with pytest.raises(AttributeError):
            item.severity = "LOW"


class TestCaseStrength:
    """Test case strength assessment logic."""

    def test_strong_case(self, full_alert_data):
        """Full alert with shared devices, high amounts, and behavioral flags should be STRONG."""
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_INV_001",
            alert_data=full_alert_data,
        )
        assert case.case_strength == "STRONG"

    def test_weak_case_low_evidence(self):
        """Alert with only low severity evidence should be WEAK."""
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_WEAK",
            alert_data={
                "alert_id": "ALT_WEAK",
                "severity": "LOW",
                "risk_score": 0.1,
                "total_amount": 5_000.0,
                "txn_count": 1,
                "reason_codes": [],
                "nodes": [],
                "edges": [],
                "shared_devices": [],
                "shared_ips": [],
            },
        )
        assert case.case_strength == "WEAK"

    def test_moderate_case(self):
        """Alert with 1-2 HIGH items but not 3+ should be MODERATE."""
        agent = CaseAssemblyAgent()
        case = agent.assemble_case(
            alert_id="ALT_MOD",
            alert_data={
                "alert_id": "ALT_MOD",
                "severity": "HIGH",
                "risk_score": 0.65,
                "total_amount": 600_000.0,
                "txn_count": 10,
                "reason_codes": ["R01: Account age < 7 days"],
                "nodes": [
                    {
                        "account_id": "AC_MOD_1",
                        "role": "SOURCE",
                        "smurf_score": 0.3,
                        "account_age_days": 30,
                        "kyc_status": "VERIFIED",
                    }
                ],
                "edges": [],
                "shared_devices": [],
                "shared_ips": [],
            },
        )
        assert case.case_strength == "MODERATE"


# ═══════════════════════════════════════════════════════════════════════════
# NarrativeAgent Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestNarrativeGeneration:
    """Test STR narrative generation (template fallback)."""

    def test_template_narrative_all_sections(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)

        assert isinstance(narrative, STRNarrative)
        assert narrative.alert_id == "ALT_INV_001"
        assert narrative.is_llm_generated is False
        assert narrative.provider == "template_fallback"

    def test_template_narrative_sections_populated(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)

        assert len(narrative.subject_info) > 0
        assert len(narrative.activity_description) > 0
        assert len(narrative.transaction_details) > 0
        assert len(narrative.supporting_evidence) > 0
        assert len(narrative.conclusion) > 0
        assert len(narrative.full_narrative) > 0

    def test_narrative_mentions_key_data(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)

        # Should mention amounts and devices
        assert "2,500,000" in narrative.full_narrative
        assert "device" in narrative.full_narrative.lower()

    def test_strong_case_mentions_str_filing(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)

        assert "STR" in narrative.conclusion or "PMLA" in narrative.conclusion

    def test_narrative_immutability(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)

        with pytest.raises(AttributeError):
            narrative.alert_id = "MODIFIED"

    def test_to_dict(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)
        d = narrative.to_dict()

        assert "alert_id" in d
        assert "full_narrative" in d
        assert "is_llm_generated" in d
        assert "provider" in d


class TestNarrativeValidation:
    """Test narrative validation logic."""

    def test_valid_narrative_passes(self, full_alert_data):
        assembler = CaseAssemblyAgent()
        case_file = assembler.assemble_case(
            alert_id="ALT_INV_001", alert_data=full_alert_data,
        )
        narrator = NarrativeAgent()
        narrative = narrator.generate_str_narrative(case_file)
        result = narrator.validate_narrative(narrative)

        assert result["valid"] is True
        assert result["issues"] == []

    def test_empty_sections_fail_validation(self):
        narrator = NarrativeAgent()
        bad_narrative = STRNarrative(
            alert_id="ALT_BAD",
            subject_info="",
            activity_description="Some activity",
            transaction_details="",
            supporting_evidence="Some evidence",
            conclusion="",
            full_narrative="Some narrative",
            is_llm_generated=False,
            provider="test",
        )
        result = narrator.validate_narrative(bad_narrative)

        assert result["valid"] is False
        assert len(result["issues"]) >= 3  # 3 empty sections

    def test_pii_leakage_detected(self):
        narrator = NarrativeAgent()
        leaked_narrative = STRNarrative(
            alert_id="ALT_PII",
            subject_info="Account AC20000001 is suspicious",
            activity_description="Activity involving AC20000002",
            transaction_details="Transfer from AC20000001 to AC20000002",
            supporting_evidence="Evidence found",
            conclusion="File STR",
            full_narrative="Account AC20000001 sent money to AC20000002",
            is_llm_generated=False,
            provider="test",
        )
        result = narrator.validate_narrative(leaked_narrative)

        assert result["valid"] is False
        pii_issues = [i for i in result["issues"] if "Raw account ID" in i]
        assert len(pii_issues) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# AlertPriorityScorer Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAlertPriorityScorerSingle:
    """Test scoring of individual alerts."""

    def test_score_returns_result(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        assert isinstance(result, AlertPriorityResult)
        assert result.alert_id == "ALT_INV_001"

    def test_score_in_range(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        assert 0.0 <= result.priority_score <= 1.0

    def test_high_risk_gets_high_score(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        # CRITICAL alert with high risk score should score highly
        assert result.priority_score > 0.5

    def test_low_risk_gets_lower_score(self, minimal_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(minimal_alert_data)
        # MEDIUM alert with low risk score
        assert result.priority_score < 0.5

    def test_score_breakdown_keys(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        expected_keys = {
            "risk_score", "amount_factor", "network_centrality",
            "evidence_diversity", "time_sensitivity",
        }
        assert set(result.score_breakdown.keys()) == expected_keys

    def test_result_immutability(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        with pytest.raises(AttributeError):
            result.priority_score = 0.0

    def test_to_dict(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        d = result.to_dict()
        assert "alert_id" in d
        assert "priority_score" in d
        assert "sar_filing_probability" in d
        assert "score_breakdown" in d

    def test_complexity_assessment(self, full_alert_data):
        scorer = AlertPriorityScorer()
        result = scorer.score_alert(full_alert_data)
        assert result.investigation_complexity in ("HIGH", "MEDIUM", "LOW")


class TestAlertPriorityScorerQueue:
    """Test queue sorting."""

    def test_queue_sorted_by_priority(self, full_alert_data, minimal_alert_data):
        scorer = AlertPriorityScorer()
        results = scorer.score_queue([minimal_alert_data, full_alert_data])
        assert len(results) == 2
        # Higher priority first
        assert results[0].priority_score >= results[1].priority_score

    def test_queue_ranks_assigned(self, full_alert_data, minimal_alert_data):
        scorer = AlertPriorityScorer()
        results = scorer.score_queue([minimal_alert_data, full_alert_data])
        assert results[0].estimated_priority_rank == 1
        assert results[1].estimated_priority_rank == 2

    def test_empty_queue(self):
        scorer = AlertPriorityScorer()
        results = scorer.score_queue([])
        assert results == []

    def test_single_alert_queue(self, full_alert_data):
        scorer = AlertPriorityScorer()
        results = scorer.score_queue([full_alert_data])
        assert len(results) == 1
        assert results[0].estimated_priority_rank == 1


class TestSARLikelihood:
    """Test SAR filing probability prediction."""

    def test_critical_high_probability(self):
        scorer = AlertPriorityScorer()
        prob = scorer.predict_sar_likelihood({
            "severity": "CRITICAL",
            "reason_codes": ["R01", "R02", "R03"],
        })
        assert prob >= 0.9

    def test_high_moderate_probability(self):
        scorer = AlertPriorityScorer()
        prob = scorer.predict_sar_likelihood({
            "severity": "HIGH",
            "reason_codes": ["R01"],
        })
        assert 0.5 <= prob <= 0.8

    def test_medium_lower_probability(self):
        scorer = AlertPriorityScorer()
        prob = scorer.predict_sar_likelihood({
            "severity": "MEDIUM",
            "reason_codes": [],
        })
        assert prob <= 0.4

    def test_low_lowest_probability(self):
        scorer = AlertPriorityScorer()
        prob = scorer.predict_sar_likelihood({
            "severity": "LOW",
            "reason_codes": [],
        })
        assert prob <= 0.2

    def test_evidence_boosts_probability(self):
        scorer = AlertPriorityScorer()
        base = scorer.predict_sar_likelihood({
            "severity": "MEDIUM", "reason_codes": [],
        })
        boosted = scorer.predict_sar_likelihood({
            "severity": "MEDIUM",
            "reason_codes": ["R01", "R02", "R03", "R04", "R05"],
        })
        assert boosted > base


# ═══════════════════════════════════════════════════════════════════════════
# GenAI Copilot (template fallback) Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInvestigateQueryFallback:
    """Test investigate_query with no LLM (template fallback)."""

    def test_returns_chat_response(self):
        svc = GenAIService(provider=None)
        result = svc.investigate_query(
            alert_id="ALT_001",
            question="Why was this flagged?",
        )
        assert isinstance(result, ChatResponse)
        assert result.is_llm_generated is False
        assert result.provider == "template_fallback"

    def test_includes_alert_id(self):
        svc = GenAIService(provider=None)
        result = svc.investigate_query(
            alert_id="ALT_TEST_123",
            question="What is the risk?",
        )
        assert "ALT_TEST_123" in result.message

    def test_includes_question(self):
        svc = GenAIService(provider=None)
        result = svc.investigate_query(
            alert_id="ALT_001",
            question="Explain the smurf score",
        )
        assert "smurf score" in result.message.lower()

    def test_with_case_context(self):
        svc = GenAIService(provider=None)
        result = svc.investigate_query(
            alert_id="ALT_001",
            question="What should I do?",
            case_context={
                "severity": "CRITICAL",
                "risk_score": 0.9,
                "reason_codes": ["R01: Account age < 7 days"],
            },
        )
        assert "CRITICAL" in result.message
        assert "R01" in result.message


class TestSuggestNextSteps:
    """Test suggest_next_steps template fallback."""

    def test_returns_chat_response(self):
        svc = GenAIService(provider=None)
        result = svc.suggest_next_steps({
            "severity": "HIGH",
            "shared_devices": ["DEV1"],
            "reason_codes": ["R01: Account age < 7 days"],
        })
        assert isinstance(result, ChatResponse)
        assert result.is_llm_generated is False

    def test_suggests_graph_review(self):
        svc = GenAIService(provider=None)
        result = svc.suggest_next_steps({
            "severity": "MEDIUM",
            "shared_devices": [],
            "reason_codes": [],
        })
        assert "graph" in result.message.lower() or "network" in result.message.lower()

    def test_device_suggestion_when_shared(self):
        svc = GenAIService(provider=None)
        result = svc.suggest_next_steps({
            "severity": "HIGH",
            "shared_devices": ["DEV1", "DEV2"],
            "reason_codes": [],
        })
        assert "device" in result.message.lower()

    def test_critical_suggests_freeze(self):
        svc = GenAIService(provider=None)
        result = svc.suggest_next_steps({
            "severity": "CRITICAL",
            "shared_devices": [],
            "reason_codes": [],
        })
        assert "freeze" in result.message.lower() or "str" in result.message.lower()


class TestGenerateSummary:
    """Test generate_summary template fallback."""

    def test_returns_chat_response(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert isinstance(result, ChatResponse)
        assert result.is_llm_generated is False

    def test_mentions_alert_id(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert "ALT_INV_001" in result.message

    def test_mentions_severity(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert "CRITICAL" in result.message

    def test_mentions_amount(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert "2,500,000" in result.message

    def test_mentions_devices(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert "device" in result.message.lower()

    def test_critical_suggests_investigation(self, full_alert_data):
        svc = GenAIService(provider=None)
        result = svc.generate_summary(full_alert_data)
        assert "investigation" in result.message.lower() or "STR" in result.message
