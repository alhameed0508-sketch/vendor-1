"""
GenAI data models and utility functions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List


def mask_account_id(value) -> str:
    """Hash-based pseudonymization for account IDs sent to external LLMs.

    Uses a truncated SHA-256 to produce consistent pseudonyms (same input
    always maps to same output) while preventing re-identification.
    Stronger than display-level masking since data leaves the org boundary.
    """
    if value is None:
        return "N/A"
    s = str(value)
    if not s:
        return "N/A"
    return f"ACCT_{hashlib.sha256(s.encode()).hexdigest()[:8]}"


@dataclass(frozen=True)
class TriageResult:
    """Immutable result from LLM triage of a cluster."""
    cluster_id: str
    llm_assessment: str        # "HIGH" | "MEDIUM" | "LOW"
    confidence_adjustment: float  # -0.10 to +0.10
    reasoning: str
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "cluster_id": self.cluster_id,
            "llm_assessment": self.llm_assessment,
            "confidence_adjustment": self.confidence_adjustment,
            "reasoning": self.reasoning,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class PatternDiscovery:
    """Immutable result from LLM pattern discovery."""
    suggested_patterns: List[Dict]
    risk_indicators: List[str]
    novel_signals: List[str]
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "suggested_patterns": self.suggested_patterns,
            "risk_indicators": self.risk_indicators,
            "novel_signals": self.novel_signals,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class ForensicAnalysis:
    """Immutable result from LLM forensic analysis."""
    alert_id: str
    executive_brief: str
    detailed_narrative: str
    regulatory_summary: str
    key_findings: List[str]
    recommended_actions: List[str]
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "executive_brief": self.executive_brief,
            "detailed_narrative": self.detailed_narrative,
            "regulatory_summary": self.regulatory_summary,
            "key_findings": self.key_findings,
            "recommended_actions": self.recommended_actions,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class ChatResponse:
    """Immutable chat response."""
    message: str
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }
