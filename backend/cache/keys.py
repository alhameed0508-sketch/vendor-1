"""
Cache key builders — centralized key naming conventions.
"""

from typing import Optional


def alert_key(alert_id: str) -> str:
    return f"alert:{alert_id}"


def alerts_list_key(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> str:
    sev = severity or "all"
    st = status or "all"
    return f"alerts:list:{sev}:{st}:{limit}"


def explanation_key(alert_id: str) -> str:
    return f"alert:{alert_id}:explanation"


def narrative_key(alert_id: str) -> str:
    return f"alert:{alert_id}:narrative"


def shap_key(alert_id: str) -> str:
    return f"alert:{alert_id}:shap"


def subgraph_key(alert_id: str) -> str:
    return f"alert:{alert_id}:subgraph"


def kpi_key() -> str:
    return "kpi:current"


def genai_analysis_key(alert_id: str) -> str:
    return f"genai:analysis:{alert_id}"


def genai_chat_key(session_id: str) -> str:
    return f"genai:chat:{session_id}"
