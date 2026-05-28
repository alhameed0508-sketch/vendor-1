"""
GenAI Service — orchestrates LLM-powered capabilities for MuleCatch.

Six capabilities:
1. Alert forensic analysis (executive brief / detailed narrative / regulatory)
2. Investigation assistant (conversational Q&A — "Ask MuleCatch")
3. Onboarding risk explanation (plain-English signal interpretation)
4. Cluster triage (LLM assessment with confidence adjustment)
5. Pattern discovery (novel mule pattern detection)
6. Investigation copilot (NL queries, next steps, summaries)

Falls back to template-based narratives when no LLM is available.

Implementation split into focused modules under services/genai_capabilities/.
This file is the public orchestrator — all external imports remain stable.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from genai.base import LLMProvider

# ── Re-export data models for backward compatibility ─────────────────────
from services.genai_capabilities.models import (  # noqa: F401
    ChatResponse,
    ForensicAnalysis,
    PatternDiscovery,
    TriageResult,
)

# ── Capability modules ───────────────────────────────────────────────────
from services.genai_capabilities import (
    chat as _chat_mod,
    copilot as _copilot_mod,
    forensic as _forensic_mod,
    onboarding as _onboarding_mod,
    patterns as _patterns_mod,
    triage as _triage_mod,
)


class GenAIService:
    """Orchestrates GenAI capabilities with template fallback."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider
        self._is_real_llm = (
            provider is not None
            and provider.provider_name != "template_fallback"
        )

    @property
    def is_enabled(self) -> bool:
        return self._is_real_llm

    @property
    def provider_name(self) -> str:
        if self._provider is None:
            return "none"
        return self._provider.provider_name

    def get_status(self) -> Dict:
        """Return current GenAI status for the status endpoint."""
        return {
            "enabled": self._is_real_llm,
            "provider": self.provider_name,
            "fallback_active": not self._is_real_llm,
        }

    # ── 1. Forensic Analysis ──────────────────────────────────────────────

    def analyze_alert(self, alert_data: Dict) -> ForensicAnalysis:
        return _forensic_mod.analyze_alert(
            self._provider, self._is_real_llm, alert_data,
        )

    # ── 2. Investigation Chat ─────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        alert_context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> ChatResponse:
        return _chat_mod.chat(
            self._provider, self._is_real_llm,
            user_message, alert_context, conversation_history,
        )

    def get_suggested_questions(self, alert_data: Optional[Dict] = None) -> List[str]:
        return _chat_mod.get_suggested_questions(alert_data)

    # ── 3. Onboarding Risk Explanation ────────────────────────────────────

    def explain_onboarding(self, assessment: Dict) -> ChatResponse:
        return _onboarding_mod.explain_onboarding(
            self._provider, self._is_real_llm, assessment,
        )

    # ── 4. Cluster Triage ────────────────────────────────────────────────

    def triage_cluster(self, alert_data: Dict) -> TriageResult:
        return _triage_mod.triage_cluster(
            self._provider, self._is_real_llm, alert_data,
        )

    # ── 5. Pattern Discovery ─────────────────────────────────────────────

    def discover_patterns(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> PatternDiscovery:
        return _patterns_mod.discover_patterns(
            self._provider, self._is_real_llm, transactions, accounts,
        )

    # ── 6. Investigation Copilot ────────────────────────────────────────

    def investigate_query(
        self,
        alert_id: str,
        question: str,
        case_context: Optional[Dict] = None,
    ) -> ChatResponse:
        return _copilot_mod.investigate_query(
            self._provider, self._is_real_llm,
            alert_id, question, case_context,
        )

    def suggest_next_steps(self, case_data: Dict) -> ChatResponse:
        return _copilot_mod.suggest_next_steps(
            self._provider, self._is_real_llm, case_data,
        )

    def generate_summary(self, case_data: Dict) -> ChatResponse:
        return _copilot_mod.generate_summary(
            self._provider, self._is_real_llm, case_data,
        )
