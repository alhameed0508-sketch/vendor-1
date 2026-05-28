"""
Cluster triage capability — LLM-powered assessment of suspicious clusters.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, Optional

from genai.base import LLMMessage, LLMProvider

from .models import TriageResult, mask_account_id as _mask
from .prompts import SYSTEM_PROMPT_TRIAGE

logger = logging.getLogger(__name__)

_ASSESSMENT_ADJUSTMENTS = {
    "HIGH": 0.10,
    "MEDIUM": 0.00,
    "LOW": -0.10,
}


def triage_cluster(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    alert_data: Dict,
) -> TriageResult:
    """LLM triage of a suspicious cluster. Returns assessment with
    confidence adjustment. Falls back to MEDIUM / 0.00 when no LLM."""
    cluster_id = alert_data.get("cluster_id", "UNKNOWN")

    if not is_real_llm:
        return _template_triage(alert_data)

    prompt = _build_triage_prompt(alert_data)
    start_ms = time.perf_counter() * 1000

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_TRIAGE),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=0.2,
            max_tokens=512,
        )
        latency = time.perf_counter() * 1000 - start_ms
        return _parse_triage_response(cluster_id, response, latency)
    except Exception as exc:
        logger.error("LLM triage failed for %s: %s", cluster_id, exc)
        return _template_triage(alert_data)


def _build_triage_prompt(alert: Dict) -> str:
    nodes = alert.get("nodes", [])
    edges = alert.get("edges", [])

    node_lines = []
    for n in nodes[:15]:
        node_lines.append(
            f"  - {_mask(n.get('account_id'))}: role={n.get('role')}, "
            f"smurf={n.get('smurf_score', 0):.2f}, "
            f"age={n.get('account_age_days')}d, kyc={n.get('kyc_status')}"
        )

    edge_lines = []
    for e in edges[:20]:
        edge_lines.append(
            f"  - {_mask(e.get('from_account'))} -> {_mask(e.get('to_account'))}: "
            f"₹{e.get('total_amount', 0):,.0f} ({e.get('txn_count')} txns, "
            f"pattern={e.get('pattern')})"
        )

    reason_codes = alert.get("reason_codes", [])

    return f"""Triage this suspicious cluster:

Cluster: {alert.get('cluster_id', 'N/A')}
Risk Score: {alert.get('risk_score', 0):.3f}
Accounts: {alert.get('account_count', 0)}
Transactions: {alert.get('txn_count', 0)}
Total Amount: ₹{alert.get('total_amount', 0):,.0f}
Shared Devices: {len(alert.get('shared_devices', []))}

Reason Codes: {', '.join(reason_codes[:5])}

Accounts:
{chr(10).join(node_lines)}

Money Flows:
{chr(10).join(edge_lines)}"""


def _parse_triage_response(
    cluster_id: str, response, latency_ms: float,
) -> TriageResult:
    text = response.content.strip()
    try:
        parsed = json.loads(text)
        assessment = parsed.get("assessment", "MEDIUM").upper()
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, AttributeError):
        # Fallback: try to extract assessment from text
        upper = text.upper()
        if "HIGH" in upper:
            assessment = "HIGH"
        elif "LOW" in upper:
            assessment = "LOW"
        else:
            assessment = "MEDIUM"
        reasoning = text[:300]

    if assessment not in _ASSESSMENT_ADJUSTMENTS:
        assessment = "MEDIUM"

    return TriageResult(
        cluster_id=cluster_id,
        llm_assessment=assessment,
        confidence_adjustment=_ASSESSMENT_ADJUSTMENTS[assessment],
        reasoning=reasoning,
        provider=response.provider,
        model=response.model,
        latency_ms=latency_ms,
        is_llm_generated=True,
    )


def _template_triage(alert_data: Dict) -> TriageResult:
    """Template fallback: return MEDIUM / no adjustment."""
    return TriageResult(
        cluster_id=alert_data.get("cluster_id", "UNKNOWN"),
        llm_assessment="MEDIUM",
        confidence_adjustment=0.00,
        reasoning="Template fallback — no LLM available for triage.",
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )
