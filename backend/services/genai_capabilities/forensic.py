"""
Forensic analysis capability — LLM-powered alert forensic narratives.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider

from .models import ForensicAnalysis, mask_account_id as _mask
from .prompts import SYSTEM_PROMPT_FORENSIC

logger = logging.getLogger(__name__)

# -- LLM generation parameters for forensic analysis -------------------------
FORENSIC_TEMPERATURE = 0.3    # Balanced creativity for narrative generation
FORENSIC_MAX_TOKENS = 2048    # Larger limit for detailed forensic reports


def analyze_alert(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    alert_data: Dict,
) -> ForensicAnalysis:
    """Generate LLM forensic analysis for an alert.
    Falls back to template narrative if LLM unavailable."""
    alert_id = alert_data.get("alert_id", "UNKNOWN")

    if not is_real_llm:
        return _template_forensic(alert_data)

    prompt = _build_forensic_prompt(alert_data)

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_FORENSIC),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=FORENSIC_TEMPERATURE,
            max_tokens=FORENSIC_MAX_TOKENS,
        )
        return _parse_forensic_response(alert_id, response)
    except Exception as exc:
        logger.error("LLM forensic analysis failed for %s: %s", alert_id, exc)
        return _template_forensic(alert_data)


def _build_forensic_prompt(alert: Dict) -> str:
    """Build the forensic analysis prompt from alert data."""
    nodes = alert.get("nodes", [])
    edges = alert.get("edges", [])
    reason_codes = alert.get("reason_codes", [])

    node_summary = []
    for n in nodes[:15]:
        node_summary.append(
            f"  - {_mask(n.get('account_id'))}: role={n.get('role')}, "
            f"smurf_score={n.get('smurf_score', 0):.2f}, "
            f"bank={n.get('bank')}, city={n.get('city')}, "
            f"age={n.get('account_age_days')}d, kyc={n.get('kyc_status')}"
        )

    edge_summary = []
    for e in edges[:20]:
        edge_summary.append(
            f"  - {_mask(e.get('from_account'))} -> {_mask(e.get('to_account'))}: "
            f"amount=₹{e.get('total_amount', 0):,.0f}, "
            f"txns={e.get('txn_count')}, pattern={e.get('pattern')}"
        )

    return f"""Analyze this MuleCatch alert:

Alert ID: {alert.get('alert_id')}
Severity: {alert.get('severity')}
Risk Score: {alert.get('risk_score', 0):.3f}
Total Amount: ₹{alert.get('total_amount', 0):,.0f}
Transaction Count: {alert.get('txn_count', 0)}
Account Count: {alert.get('account_count', 0)}
GNN Score: {alert.get('gnn_score', 'N/A')}
Shared Devices: {len(alert.get('shared_devices', []))}
Shared IPs: {len(alert.get('shared_ips', []))}

Reason Codes:
{chr(10).join(f'  - {rc}' for rc in reason_codes)}

Network Nodes:
{chr(10).join(node_summary)}

Money Flows:
{chr(10).join(edge_summary)}

Generate a forensic analysis with sections:
## Executive Brief
## Detailed Narrative
## Regulatory Summary
## Key Findings
## Recommended Actions"""


def _parse_forensic_response(alert_id: str, response) -> ForensicAnalysis:
    """Parse LLM response into structured ForensicAnalysis."""
    text = response.content
    sections = {
        "executive_brief": "",
        "detailed_narrative": "",
        "regulatory_summary": "",
    }
    key_findings: List[str] = []
    recommended_actions: List[str] = []

    current_section = None
    current_lines: List[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        lower = stripped.lower()

        if "executive brief" in lower and stripped.startswith("#"):
            if current_section:
                _store_section(current_section, current_lines, sections,
                               key_findings, recommended_actions)
            current_section = "executive_brief"
            current_lines = []
        elif "detailed narrative" in lower and stripped.startswith("#"):
            if current_section:
                _store_section(current_section, current_lines, sections,
                               key_findings, recommended_actions)
            current_section = "detailed_narrative"
            current_lines = []
        elif "regulatory summary" in lower and stripped.startswith("#"):
            if current_section:
                _store_section(current_section, current_lines, sections,
                               key_findings, recommended_actions)
            current_section = "regulatory_summary"
            current_lines = []
        elif "key findings" in lower and stripped.startswith("#"):
            if current_section:
                _store_section(current_section, current_lines, sections,
                               key_findings, recommended_actions)
            current_section = "key_findings"
            current_lines = []
        elif "recommended actions" in lower and stripped.startswith("#"):
            if current_section:
                _store_section(current_section, current_lines, sections,
                               key_findings, recommended_actions)
            current_section = "recommended_actions"
            current_lines = []
        else:
            current_lines.append(line)

    # Store final section
    if current_section:
        _store_section(current_section, current_lines, sections,
                       key_findings, recommended_actions)

    # Fallback: if parsing got nothing, use full text as narrative
    if not any(sections.values()):
        sections["detailed_narrative"] = text
        sections["executive_brief"] = text[:300]

    return ForensicAnalysis(
        alert_id=alert_id,
        executive_brief=sections["executive_brief"],
        detailed_narrative=sections["detailed_narrative"],
        regulatory_summary=sections["regulatory_summary"],
        key_findings=key_findings or ["See detailed narrative"],
        recommended_actions=recommended_actions or ["Review alert details"],
        provider=response.provider,
        model=response.model,
        latency_ms=response.latency_ms,
        is_llm_generated=True,
    )


def _store_section(
    section_name: str,
    lines: List[str],
    sections: Dict,
    key_findings: List[str],
    recommended_actions: List[str],
) -> None:
    text = "\n".join(lines).strip()
    if section_name == "key_findings":
        for line in lines:
            stripped = line.strip().lstrip("-*• ")
            if stripped:
                key_findings.append(stripped)
    elif section_name == "recommended_actions":
        for line in lines:
            stripped = line.strip().lstrip("-*•0123456789. ")
            if stripped:
                recommended_actions.append(stripped)
    else:
        sections[section_name] = text


def _template_forensic(alert_data: Dict) -> ForensicAnalysis:
    """Generate template-based forensic analysis (fallback)."""
    from explainability.narrative_generator import generate_narrative

    alert_id = alert_data.get("alert_id", "UNKNOWN")
    narrative = generate_narrative(alert_data)

    return ForensicAnalysis(
        alert_id=alert_id,
        executive_brief=narrative.executive_brief,
        detailed_narrative=narrative.detailed_narrative,
        regulatory_summary=narrative.regulatory_summary,
        key_findings=narrative.key_findings,
        recommended_actions=narrative.recommended_actions,
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )
