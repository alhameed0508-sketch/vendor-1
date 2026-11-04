"""
Cache key builders — centralized key naming conventions.
"""


def alert_key(alert_id: str) -> str:
    return f"alert:{alert_id}"


def explanation_key(alert_id: str) -> str:
    return f"alert:{alert_id}:explanation"


def narrative_key(alert_id: str) -> str:
    return f"alert:{alert_id}:narrative"


def shap_key(alert_id: str) -> str:
    return f"alert:{alert_id}:shap"


def subgraph_key(alert_id: str) -> str:
    return f"alert:{alert_id}:subgraph"
