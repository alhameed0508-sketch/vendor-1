"""
Investigation chat capability — conversational Q&A and question suggestions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider

from .models import ChatResponse
from .prompts import SYSTEM_PROMPT_CHAT

logger = logging.getLogger(__name__)


def chat(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    user_message: str,
    alert_context: Optional[Dict] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> ChatResponse:
    """Investigation assistant chat.
    Falls back to a helpful static response if LLM unavailable."""
    if not is_real_llm:
        return ChatResponse(
            message=(
                "GenAI is not configured. Set GENAI_ENABLED=true and provide "
                "an API key to enable the investigation assistant. "
                "You can still use the template-based narratives and "
                "explainability panels for alert analysis."
            ),
            provider="template_fallback",
            model="template",
            latency_ms=0.0,
            is_llm_generated=False,
        )

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT_CHAT)]

    # Add alert context if provided
    if alert_context:
        context_str = format_alert_context(alert_context)
        messages.append(LLMMessage(
            role="system",
            content=f"Current alert context:\n{context_str}",
        ))

    # Add conversation history
    if conversation_history:
        for msg in conversation_history[-10:]:  # Keep last 10 messages
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append(LLMMessage(role=role, content=msg["content"]))

    messages.append(LLMMessage(role="user", content=user_message))

    try:
        response = provider.generate(
            messages=messages,
            temperature=0.4,
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
        logger.error("LLM chat failed: %s", exc)
        return ChatResponse(
            message="I encountered an error processing your request. Please try again.",
            provider="error",
            model="none",
            latency_ms=0.0,
            is_llm_generated=False,
        )


def format_alert_context(alert: Dict) -> str:
    """Format alert data for chat context injection."""
    return (
        f"Alert: {alert.get('alert_id', 'N/A')}\n"
        f"Severity: {alert.get('severity', 'N/A')}\n"
        f"Risk Score: {alert.get('risk_score', 0):.3f}\n"
        f"Accounts: {alert.get('account_count', 0)}\n"
        f"Total Amount: ₹{alert.get('total_amount', 0):,.0f}\n"
        f"Reason Codes: {', '.join(alert.get('reason_codes', [])[:5])}"
    )


def get_suggested_questions(alert_data: Optional[Dict] = None) -> List[str]:
    """Return suggested questions based on alert context."""
    base_questions = [
        "What does the risk score mean for this alert?",
        "Explain the mule network structure in this cluster.",
        "What RBI regulations apply to this suspicious activity?",
        "What should I do as the next investigation step?",
        "How confident is MuleCatch in this detection?",
    ]
    if alert_data:
        severity = alert_data.get("severity", "")
        if severity == "CRITICAL":
            base_questions[0] = "Why is this alert classified as CRITICAL?"
        reason_codes = alert_data.get("reason_codes", [])
        if reason_codes:
            first_code = reason_codes[0].split(":")[0] if ":" in reason_codes[0] else reason_codes[0]
            base_questions[1] = f"Explain rule {first_code} — why did it trigger?"
    return base_questions
