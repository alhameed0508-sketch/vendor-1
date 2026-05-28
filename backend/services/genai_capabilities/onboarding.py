"""
Onboarding risk explanation capability.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from genai.base import LLMMessage, LLMProvider

from .models import ChatResponse, mask_account_id as _mask
from .prompts import SYSTEM_PROMPT_ONBOARDING

logger = logging.getLogger(__name__)


def explain_onboarding(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    assessment: Dict,
) -> ChatResponse:
    """Generate plain-English explanation of onboarding risk assessment.
    Falls back to a structured template explanation."""
    if not is_real_llm:
        return _template_onboarding_explanation(assessment)

    prompt = _build_onboarding_prompt(assessment)

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_ONBOARDING),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return ChatResponse(
            message=response.content,
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            is_llm_generated=True,
        )
    except Exception as exc:
        logger.error("LLM onboarding explanation failed: %s", exc)
        return _template_onboarding_explanation(assessment)


def _build_onboarding_prompt(assessment: Dict) -> str:
    signals = assessment.get("signals", [])
    signal_lines = []
    for sig in signals:
        signal_lines.append(
            f"  - {sig.get('signal', 'unknown')}: "
            f"score={sig.get('score', 0):.2f}, "
            f"weight={sig.get('weight', 0)}, "
            f"weighted={sig.get('weighted', 0):.4f}"
        )
    reason_codes = assessment.get("reason_codes", [])
    return f"""Explain this onboarding risk assessment in plain English:

Account: {_mask(assessment.get('account_id', 'N/A'))}
Risk Score: {assessment.get('risk_score', 0):.2f}
Risk Level: {assessment.get('risk_level', 'N/A')}
Recommendation: {assessment.get('recommendation', 'N/A')}

Triggered Reason Codes:
{chr(10).join(f'  - {rc}' for rc in reason_codes)}

Signal Breakdown:
{chr(10).join(signal_lines)}

Explain which signals contributed most to the risk score, what they mean
in practical terms, and what the bank should do next."""


def _template_onboarding_explanation(assessment: Dict) -> ChatResponse:
    """Template-based onboarding explanation."""
    risk_level = assessment.get("risk_level", "UNKNOWN")
    risk_score = assessment.get("risk_score", 0)
    reason_codes = assessment.get("reason_codes", [])
    signals = assessment.get("signals", [])

    # Sort signals by weighted score descending
    top_signals = sorted(
        signals, key=lambda s: s.get("weighted", 0), reverse=True
    )[:5]

    lines = [
        f"Risk Assessment: {risk_level} ({risk_score:.0%} risk score)",
        "",
    ]

    if reason_codes:
        lines.append("Flags triggered:")
        for rc in reason_codes:
            lines.append(f"  - {rc}")
        lines.append("")

    if top_signals:
        lines.append("Top contributing signals:")
        for sig in top_signals:
            name = sig.get("signal", "").replace("_", " ").title()
            score = sig.get("score", 0)
            lines.append(f"  - {name}: {score:.2f}")
        lines.append("")

    lines.append(
        f"Recommendation: {assessment.get('recommendation', 'Review manually')}"
    )

    return ChatResponse(
        message="\n".join(lines),
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )
