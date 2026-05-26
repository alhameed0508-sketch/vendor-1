"""
Tests for GenAI integration — provider abstraction, service, factory, fallback.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import pytest
from genai.base import LLMMessage, LLMResponse, TemplateProvider
from genai.factory import create_llm_provider
from services.genai_service import GenAIService, TriageResult, PatternDiscovery
from genai.base import LLMProvider


class _MockLLMProviderForTriage(LLMProvider):
    """Local mock for triage/pattern tests with custom response text."""
    def __init__(self, response_text: str):
        self._text = response_text

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, messages, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=self._text, model="mock-model", provider="mock",
            prompt_tokens=10, completion_tokens=20, latency_ms=5.0,
        )

MockLLMProvider = _MockLLMProviderForTriage


# ── Provider tests ───────────────────────────────────────────────────────────


class TestTemplateProvider:
    def test_provider_name(self, template_provider):
        assert template_provider.provider_name == "template_fallback"

    def test_generate_returns_empty(self, template_provider):
        resp = template_provider.generate([LLMMessage(role="user", content="test")])
        assert isinstance(resp, LLMResponse)
        assert resp.content == ""
        assert resp.provider == "template_fallback"

    def test_health_check_always_true(self, template_provider):
        assert template_provider.health_check() is True


class TestMockProvider:
    def test_provider_name(self, mock_provider):
        assert mock_provider.provider_name == "mock"

    def test_generate_returns_content(self, mock_provider):
        resp = mock_provider.generate([LLMMessage(role="user", content="test")])
        assert "Executive Brief" in resp.content
        assert resp.provider == "mock"
        assert resp.prompt_tokens == 10
        assert resp.completion_tokens == 20

    def test_health_check_succeeds(self, mock_provider):
        assert mock_provider.health_check() is True


class TestFailingProvider:
    def test_generate_raises(self, failing_provider):
        with pytest.raises(RuntimeError, match="unavailable"):
            failing_provider.generate([LLMMessage(role="user", content="test")])

    def test_health_check_returns_false(self, failing_provider):
        assert failing_provider.health_check() is False


# ── Factory tests ────────────────────────────────────────────────────────────


class TestFactory:
    def test_disabled_returns_none(self):
        """When genai_enabled=False, factory returns None."""

        class MockSettings:
            genai_enabled = False

        provider = create_llm_provider(MockSettings())
        assert provider is None

    def test_enabled_no_key_returns_template(self):
        """When enabled but no API key, returns TemplateProvider."""

        class MockSettings:
            genai_enabled = True
            genai_api_key = ""
            genai_provider = "gemini"
            genai_model = ""

        provider = create_llm_provider(MockSettings())
        assert isinstance(provider, TemplateProvider)

    def test_unknown_provider_returns_template(self):
        """Unknown provider name falls back to TemplateProvider."""

        class MockSettings:
            genai_enabled = True
            genai_api_key = "test-key"
            genai_provider = "unknown_provider"
            genai_model = ""

        provider = create_llm_provider(MockSettings())
        assert isinstance(provider, TemplateProvider)


# ── GenAI Service tests ──────────────────────────────────────────────────────


class TestGenAIServiceWithMock:
    """Test GenAIService with a mock LLM provider."""

    def test_is_enabled(self, mock_provider):
        svc = GenAIService(provider=mock_provider)
        assert svc.is_enabled is True

    def test_get_status(self, mock_provider):
        svc = GenAIService(provider=mock_provider)
        status = svc.get_status()
        assert status["enabled"] is True
        assert status["provider"] == "mock"
        assert status["fallback_active"] is False

    def test_analyze_alert(self, mock_provider, sample_alert_data):
        svc = GenAIService(provider=mock_provider)
        result = svc.analyze_alert(sample_alert_data)
        assert result.alert_id == "ALT_TEST12345"
        assert result.is_llm_generated is True
        assert result.provider == "mock"
        assert "critical" in result.executive_brief.lower() or len(result.executive_brief) > 0

    def test_chat(self, mock_provider):
        svc = GenAIService(provider=mock_provider)
        result = svc.chat("What does this alert mean?")
        assert result.is_llm_generated is True
        assert len(result.message) > 0

    def test_chat_with_context(self, mock_provider, sample_alert_data):
        svc = GenAIService(provider=mock_provider)
        result = svc.chat(
            "Explain the risk score",
            alert_context=sample_alert_data,
        )
        assert result.is_llm_generated is True

    def test_explain_onboarding(self, mock_provider, sample_onboarding_assessment):
        svc = GenAIService(provider=mock_provider)
        result = svc.explain_onboarding(sample_onboarding_assessment)
        assert result.is_llm_generated is True
        assert len(result.message) > 0


class TestGenAIServiceFallback:
    """Test GenAIService without an LLM (template fallback)."""

    def test_is_not_enabled(self):
        svc = GenAIService(provider=None)
        assert svc.is_enabled is False

    def test_status_shows_fallback(self):
        svc = GenAIService(provider=None)
        status = svc.get_status()
        assert status["enabled"] is False
        assert status["fallback_active"] is True

    def test_analyze_falls_back_to_template(self, sample_alert_data):
        svc = GenAIService(provider=None)
        result = svc.analyze_alert(sample_alert_data)
        assert result.is_llm_generated is False
        assert result.provider == "template_fallback"
        assert len(result.executive_brief) > 0
        assert len(result.detailed_narrative) > 0

    def test_chat_returns_guidance(self):
        svc = GenAIService(provider=None)
        result = svc.chat("Test question")
        assert result.is_llm_generated is False
        assert "not configured" in result.message.lower() or "genai" in result.message.lower()

    def test_explain_onboarding_template(self, sample_onboarding_assessment):
        svc = GenAIService(provider=None)
        result = svc.explain_onboarding(sample_onboarding_assessment)
        assert result.is_llm_generated is False
        assert "HIGH" in result.message or "Risk" in result.message

    def test_template_provider_fallback(self, template_provider, sample_alert_data):
        svc = GenAIService(provider=template_provider)
        assert svc.is_enabled is False
        result = svc.analyze_alert(sample_alert_data)
        assert result.is_llm_generated is False

    def test_suggested_questions(self, sample_alert_data):
        svc = GenAIService(provider=None)
        questions = svc.get_suggested_questions(sample_alert_data)
        assert len(questions) == 5
        assert any("CRITICAL" in q for q in questions)


class TestGenAIServiceWithFailingProvider:
    """Test GenAIService when LLM throws errors."""

    def test_analyze_falls_back_on_error(self, failing_provider, sample_alert_data):
        svc = GenAIService(provider=failing_provider)
        result = svc.analyze_alert(sample_alert_data)
        # Should gracefully fall back to template
        assert result.is_llm_generated is False
        assert result.provider == "template_fallback"

    def test_chat_returns_error_message(self, failing_provider):
        svc = GenAIService(provider=failing_provider)
        result = svc.chat("Test")
        assert "error" in result.message.lower() or not result.is_llm_generated

    def test_explain_onboarding_falls_back(self, failing_provider, sample_onboarding_assessment):
        svc = GenAIService(provider=failing_provider)
        result = svc.explain_onboarding(sample_onboarding_assessment)
        assert result.is_llm_generated is False


# ── ForensicAnalysis result tests ────────────────────────────────────────────


class TestForensicAnalysisResult:
    def test_to_dict(self, mock_provider, sample_alert_data):
        svc = GenAIService(provider=mock_provider)
        result = svc.analyze_alert(sample_alert_data)
        d = result.to_dict()
        assert "alert_id" in d
        assert "executive_brief" in d
        assert "is_llm_generated" in d
        assert isinstance(d["key_findings"], list)
        assert isinstance(d["recommended_actions"], list)


# ── Triage tests ────────────────────────────────────────────────────────────


class TestTriageWithMock:
    """Test cluster triage with mock LLM provider."""

    def test_triage_with_mock(self, sample_alert_data):
        """Mock provider returns text, triage should parse assessment."""
        triage_provider = MockLLMProvider(
            response_text='{"assessment": "HIGH", "reasoning": "Strong mule indicators."}'
        )
        svc = GenAIService(provider=triage_provider)
        result = svc.triage_cluster(sample_alert_data)
        assert isinstance(result, TriageResult)
        assert result.is_llm_generated is True
        assert result.llm_assessment == "HIGH"
        assert result.confidence_adjustment == 0.10
        assert len(result.reasoning) > 0

    def test_triage_low_assessment(self, sample_alert_data):
        provider = MockLLMProvider(
            response_text='{"assessment": "LOW", "reasoning": "Likely legitimate."}'
        )
        svc = GenAIService(provider=provider)
        result = svc.triage_cluster(sample_alert_data)
        assert result.llm_assessment == "LOW"
        assert result.confidence_adjustment == -0.10


class TestTriageFallback:
    """Test triage template fallback."""

    def test_triage_template_fallback(self, sample_alert_data):
        svc = GenAIService(provider=None)
        result = svc.triage_cluster(sample_alert_data)
        assert isinstance(result, TriageResult)
        assert result.is_llm_generated is False
        assert result.llm_assessment == "MEDIUM"
        assert result.confidence_adjustment == 0.00

    def test_triage_result_immutability(self, sample_alert_data):
        svc = GenAIService(provider=None)
        result = svc.triage_cluster(sample_alert_data)
        with pytest.raises(AttributeError):
            result.llm_assessment = "HIGH"

    def test_triage_to_dict(self, sample_alert_data):
        svc = GenAIService(provider=None)
        result = svc.triage_cluster(sample_alert_data)
        d = result.to_dict()
        assert "cluster_id" in d
        assert "llm_assessment" in d
        assert "confidence_adjustment" in d
        assert "reasoning" in d

    def test_triage_with_failing_provider(self, failing_provider, sample_alert_data):
        svc = GenAIService(provider=failing_provider)
        result = svc.triage_cluster(sample_alert_data)
        # Should gracefully fall back to template
        assert result.is_llm_generated is False
        assert result.llm_assessment == "MEDIUM"


# ── Pattern discovery tests ─────────────────────────────────────────────────


class TestPatternDiscovery:
    def test_discover_patterns_mock(self):
        provider = MockLLMProvider(
            response_text=json.dumps({
                "patterns": [{"name": "circular_upi", "description": "Circular UPI transfers", "risk_level": "HIGH"}],
                "risk_indicators": ["rapid round-trip"],
                "novel_signals": ["UPI handle reuse"],
            })
        )
        svc = GenAIService(provider=provider)
        result = svc.discover_patterns(
            transactions=[{"from_account": "A", "to_account": "B", "amount": 1000, "pattern": "NORMAL"}],
            accounts=[{"account_id": "A", "role": "LEGIT"}],
        )
        assert isinstance(result, PatternDiscovery)
        assert result.is_llm_generated is True
        assert len(result.suggested_patterns) == 1
        assert len(result.risk_indicators) == 1

    def test_discover_patterns_fallback(self):
        svc = GenAIService(provider=None)
        result = svc.discover_patterns(transactions=[], accounts=[])
        assert result.is_llm_generated is False
        assert result.suggested_patterns == []
        assert result.risk_indicators == []

    def test_discover_patterns_to_dict(self):
        svc = GenAIService(provider=None)
        result = svc.discover_patterns(transactions=[], accounts=[])
        d = result.to_dict()
        assert "suggested_patterns" in d
        assert "risk_indicators" in d
        assert "novel_signals" in d
