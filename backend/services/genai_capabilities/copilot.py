"""
Investigation copilot capability — natural language queries, next steps, summaries.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider

from .models import ChatResponse
from .prompts import SYSTEM_PROMPT_INVESTIGATION

logger = logging.getLogger(__name__)

# -- LLM generation parameters for investigation copilot ---------------------
COPILOT_TEMPERATURE = 0.3      # Balanced creativity for investigation Q&A
COPILOT_MAX_TOKENS = 1024      # Max response length for investigation queries
COPILOT_SUMMARY_MAX_TOKENS = 512  # Max response length for summaries and next steps


def investigate_query(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    alert_id: str,
    question: str,
    case_context: Optional[Dict] = None,
) -> ChatResponse:
    """Natural language querying of case data for investigation."""
    if not is_real_llm:
        return _template_investigate_query(alert_id, question, case_context)

    context_str = ""
    if case_context:
        context_str = (
            f"\nCase context for alert {alert_id}:\n"
            f"  Severity: {case_context.get('severity', 'N/A')}\n"
            f"  Risk Score: {case_context.get('risk_score', 'N/A')}\n"
            f"  Accounts: {case_context.get('account_count', 'N/A')}\n"
            f"  Amount: INR {case_context.get('total_amount', 0):,.0f}\n"
            f"  Reason Codes: {', '.join(case_context.get('reason_codes', [])[:5])}\n"
        )

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_INVESTIGATION),
                LLMMessage(
                    role="user",
                    content=f"Alert: {alert_id}\n{context_str}\nQuestion: {question}",
                ),
            ],
            temperature=COPILOT_TEMPERATURE,
            max_tokens=COPILOT_MAX_TOKENS,
        )
        return ChatResponse(
            message=response.content,
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            is_llm_generated=True,
        )
    except Exception as exc:
        logger.error("LLM investigate_query failed for %s: %s", alert_id, exc)
        return _template_investigate_query(alert_id, question, case_context)


def _template_investigate_query(
    alert_id: str, question: str, case_context: Optional[Dict] = None,
) -> ChatResponse:
    """Template fallback for investigation queries."""
    lines = [f"Investigation query for alert {alert_id}:"]
    lines.append(f"Question: {question}")
    lines.append("")

    if case_context:
        severity = case_context.get("severity", "UNKNOWN")
        risk_score = case_context.get("risk_score", 0)
        reason_codes = case_context.get("reason_codes", [])
        lines.append(f"Alert severity: {severity}, risk score: {risk_score}")
        if reason_codes:
            lines.append("Key indicators:")
            for rc in reason_codes[:5]:
                lines.append(f"  - {rc}")
        lines.append("")
        lines.append(
            "For detailed AI-powered investigation, configure a GenAI "
            "provider (set GENAI_ENABLED=true with an API key)."
        )
    else:
        lines.append(
            "No case context provided. Supply alert data for a richer answer. "
            "GenAI copilot is not configured — set GENAI_ENABLED=true."
        )

    return ChatResponse(
        message="\n".join(lines),
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )


def suggest_next_steps(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    case_data: Dict,
) -> ChatResponse:
    """AI recommends investigation actions based on evidence gaps."""
    if not is_real_llm:
        return _template_next_steps(case_data)

    prompt = (
        f"Given this case data, suggest the top 3-5 investigation next steps:\n"
        f"  Severity: {case_data.get('severity', 'N/A')}\n"
        f"  Risk Score: {case_data.get('risk_score', 'N/A')}\n"
        f"  Accounts: {case_data.get('account_count', 'N/A')}\n"
        f"  Amount: INR {case_data.get('total_amount', 0):,.0f}\n"
        f"  Shared Devices: {len(case_data.get('shared_devices', []))}\n"
        f"  Reason Codes: {', '.join(case_data.get('reason_codes', [])[:5])}\n"
    )

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_INVESTIGATION),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=COPILOT_TEMPERATURE,
            max_tokens=COPILOT_SUMMARY_MAX_TOKENS,
        )
        return ChatResponse(
            message=response.content,
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            is_llm_generated=True,
        )
    except Exception as exc:
        logger.error("LLM suggest_next_steps failed: %s", exc)
        return _template_next_steps(case_data)


def _template_next_steps(case_data: Dict) -> ChatResponse:
    """Rule-based next step suggestions."""
    steps: List[str] = []
    severity = case_data.get("severity", "").upper()
    shared_devices = case_data.get("shared_devices", [])
    reason_codes = case_data.get("reason_codes", [])

    # Always suggest graph analysis
    steps.append("Review network graph for additional connected accounts")

    # Device-based suggestions
    if shared_devices:
        steps.append(
            f"Investigate {len(shared_devices)} shared device(s) for "
            "coordinated access patterns"
        )

    # Transaction review
    steps.append("Review transaction timeline for structuring patterns")

    # Severity-based
    if severity in ("CRITICAL", "HIGH"):
        steps.append("Consider immediate account freeze per PMLA 2002 Section 17")
        steps.append("Prepare STR filing for FIU-IND submission")
    else:
        steps.append("Schedule customer contact for enhanced due diligence")

    # Rule-specific
    for rc in reason_codes[:3]:
        if "kyc" in rc.lower():
            steps.append("Request updated KYC documentation from branch")
            break

    return ChatResponse(
        message="Suggested next steps:\n" + "\n".join(
            f"  {i + 1}. {s}" for i, s in enumerate(steps)
        ),
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )


def generate_summary(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    case_data: Dict,
) -> ChatResponse:
    """One-paragraph executive summary for supervisors."""
    if not is_real_llm:
        return _template_summary(case_data)

    prompt = (
        "Generate a one-paragraph executive summary (3-4 sentences) for "
        "a supervisor reviewing this alert:\n"
        f"  Alert: {case_data.get('alert_id', 'N/A')}\n"
        f"  Severity: {case_data.get('severity', 'N/A')}\n"
        f"  Risk Score: {case_data.get('risk_score', 0):.3f}\n"
        f"  Accounts: {case_data.get('account_count', 0)}\n"
        f"  Amount: INR {case_data.get('total_amount', 0):,.0f}\n"
        f"  Shared Devices: {len(case_data.get('shared_devices', []))}\n"
        f"  Reason Codes: {', '.join(case_data.get('reason_codes', [])[:5])}\n"
    )

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_INVESTIGATION),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=COPILOT_TEMPERATURE,
            max_tokens=COPILOT_SUMMARY_MAX_TOKENS,
        )
        return ChatResponse(
            message=response.content,
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            is_llm_generated=True,
        )
    except Exception as exc:
        logger.error("LLM generate_summary failed: %s", exc)
        return _template_summary(case_data)


def _template_summary(case_data: Dict) -> ChatResponse:
    """Template-based executive summary."""
    alert_id = case_data.get("alert_id", "N/A")
    severity = case_data.get("severity", "UNKNOWN")
    risk_score = case_data.get("risk_score", 0)
    account_count = case_data.get("account_count", 0)
    total_amount = case_data.get("total_amount", 0)
    device_count = len(case_data.get("shared_devices", []))
    reason_codes = case_data.get("reason_codes", [])

    summary = (
        f"Alert {alert_id} is rated {severity} with a risk score of "
        f"{risk_score:.3f}, involving {account_count} account(s) and "
        f"INR {total_amount:,.0f} in suspicious transactions. "
    )
    if device_count > 0:
        summary += (
            f"{device_count} shared device(s) indicate potential "
            "coordinated activity. "
        )
    if reason_codes:
        summary += f"Key indicators: {'; '.join(reason_codes[:3])}. "

    if severity in ("CRITICAL", "HIGH"):
        summary += "Immediate investigation and potential STR filing recommended."
    else:
        summary += "Routine investigation review recommended."

    return ChatResponse(
        message=summary,
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )
