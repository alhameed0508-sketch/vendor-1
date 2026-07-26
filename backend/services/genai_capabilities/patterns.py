"""
Pattern discovery capability — LLM-powered detection of novel mule patterns.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider

from .models import PatternDiscovery, mask_account_id as _mask
from .prompts import SYSTEM_PROMPT_PATTERN_DISCOVERY

logger = logging.getLogger(__name__)

# -- LLM generation parameters for pattern discovery -------------------------
PATTERNS_TEMPERATURE = 0.4    # Higher temperature for creative pattern discovery
PATTERNS_MAX_TOKENS = 1024    # Max response length for pattern output


def discover_patterns(
    provider: Optional[LLMProvider],
    is_real_llm: bool,
    transactions: List[Dict],
    accounts: List[Dict],
) -> PatternDiscovery:
    """LLM-powered discovery of novel mule patterns in a batch of data.
    Falls back to empty pattern list when no LLM available."""
    if not is_real_llm:
        return _template_pattern_discovery()

    prompt = _build_pattern_prompt(transactions, accounts)
    start_ms = time.perf_counter() * 1000

    try:
        response = provider.generate(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT_PATTERN_DISCOVERY),
                LLMMessage(role="user", content=prompt),
            ],
            temperature=PATTERNS_TEMPERATURE,
            max_tokens=PATTERNS_MAX_TOKENS,
        )
        latency = time.perf_counter() * 1000 - start_ms
        return _parse_pattern_response(response, latency)
    except Exception as exc:
        logger.error("LLM pattern discovery failed: %s", exc)
        return _template_pattern_discovery()


def _build_pattern_prompt(
    transactions: List[Dict], accounts: List[Dict],
) -> str:
    # Summarize rather than send raw data
    total_txns = len(transactions)
    total_accounts = len(accounts)
    roles: Dict[str, int] = {}
    for a in accounts:
        role = a.get("role", "UNKNOWN")
        roles[role] = roles.get(role, 0) + 1

    amounts = [float(t["amount"]) for t in transactions]
    avg_amount = sum(amounts) / max(len(amounts), 1)
    max_amount = max(amounts) if amounts else 0

    patterns: Dict[str, int] = {}
    for t in transactions:
        p = t.get("pattern", "NORMAL")
        patterns[p] = patterns.get(p, 0) + 1

    return f"""Analyze this transaction batch for novel mule patterns:

Summary:
- {total_accounts} accounts, {total_txns} transactions
- Average transaction: ₹{avg_amount:,.0f}, Max: ₹{max_amount:,.0f}
- Account roles: {roles}
- Transaction patterns: {patterns}

Sample transactions (first 20):
{chr(10).join(
    f"  {_mask(t.get('from_account'))} -> {_mask(t.get('to_account'))}: ₹{float(t['amount']):,.0f} ({t.get('pattern', 'N/A')})"
    for t in transactions[:20]
)}

Identify novel patterns, risk indicators, and signals not covered
by standard MuleHunter.AI rules (R01-R20)."""


def _parse_pattern_response(response, latency_ms: float) -> PatternDiscovery:
    text = response.content.strip()
    try:
        parsed = json.loads(text)
        return PatternDiscovery(
            suggested_patterns=parsed.get("patterns", []),
            risk_indicators=parsed.get("risk_indicators", []),
            novel_signals=parsed.get("novel_signals", []),
            provider=response.provider,
            model=response.model,
            latency_ms=latency_ms,
            is_llm_generated=True,
        )
    except (json.JSONDecodeError, AttributeError):
        return PatternDiscovery(
            suggested_patterns=[],
            risk_indicators=[],
            novel_signals=[text[:300] if text else "Parse failed"],
            provider=response.provider,
            model=response.model,
            latency_ms=latency_ms,
            is_llm_generated=True,
        )


def _template_pattern_discovery() -> PatternDiscovery:
    """Template fallback: return empty pattern list."""
    return PatternDiscovery(
        suggested_patterns=[],
        risk_indicators=[],
        novel_signals=[],
        provider="template_fallback",
        model="template",
        latency_ms=0.0,
        is_llm_generated=False,
    )
