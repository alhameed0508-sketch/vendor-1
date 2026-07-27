"""
Graph service — graph analytics and statistics.
"""

from typing import Dict, List


class GraphService:
    """Business logic for graph statistics."""

    def get_stats(self, dataset: Dict, alerts: List[Dict]) -> Dict:
        """Compute graph statistics from dataset and alerts."""
        return {
            "total_accounts": len(dataset["accounts"]),
            "total_transactions": len(dataset["transactions"]),
            "suspicious_transactions": dataset.get("stats", {}).get("suspicious_transactions", 0),
            "mule_clusters_detected": len(
                [a for a in alerts if a["severity"] in ("CRITICAL", "HIGH")]
            ),
            "total_alerts": len(alerts),
            "critical": len([a for a in alerts if a["severity"] == "CRITICAL"]),
            "high": len([a for a in alerts if a["severity"] == "HIGH"]),
            "medium": len([a for a in alerts if a["severity"] == "MEDIUM"]),
        }
