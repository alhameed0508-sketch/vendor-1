"""
Per-account analysis of an uploaded CBS dataset and the alerts the pipeline produced for it.

Shared by ``POST /csv-upload/analyze`` and the assessment ledger, so both read the same
risk score, mule classification and cluster for every account.
"""

from collections import defaultdict
from typing import Dict, List


def analyze_dataset(dataset: Dict, alerts: List[Dict]) -> Dict:
    """Return per_account, aggregate and clusters for ``dataset`` given its ``alerts``."""
    transactions = dataset.get("transactions", [])
    accounts = dataset.get("accounts", [])

    # Build account lookup
    acc_map = {a["account_id"]: a for a in accounts}
    account_ids = set(acc_map.keys())

    # Map accounts to their alert memberships and classifications
    account_alerts: dict = defaultdict(list)
    for alert in alerts:
        for node in alert.get("nodes", []):
            acc_id = node.get("account_id", "")
            if acc_id in account_ids:
                account_alerts[acc_id].append(alert)

    # Build per-account analysis
    per_account = []
    for acc in accounts:
        acc_id = acc["account_id"]
        related_alerts = account_alerts.get(acc_id, [])

        # Aggregate risk from all alerts this account appears in
        max_risk = 0.0
        all_reason_codes: list = []
        mule_classification = "CLEAN"
        smurf_score = 0.0
        node_data = {}

        for alert in related_alerts:
            max_risk = max(max_risk, alert.get("risk_score", 0))
            all_reason_codes.extend(alert.get("reason_codes", []))

            # Get node-level data for this account
            for node in alert.get("nodes", []):
                if node.get("account_id") == acc_id:
                    smurf_score = max(smurf_score, node.get("smurf_score", 0))
                    node_data = node
                    break

            # Get mule classification from alert
            mc = alert.get("mule_classification", {})
            if mc:
                for member in mc.get("account_classifications", []):
                    if member.get("account_id") == acc_id:
                        role = member.get("classification", "UNKNOWN")
                        if role in ("COMPLICIT_MULE", "COMPLICIT"):
                            mule_classification = "COMPLICIT"
                        elif role in ("EXPLOITED_MULE", "EXPLOITED") and mule_classification != "COMPLICIT":
                            mule_classification = "EXPLOITED"
                        elif role == "UNKNOWN" and mule_classification == "CLEAN":
                            mule_classification = "EXPLOITED"
                        break

        # Deduplicate reason codes
        unique_reasons = list(dict.fromkeys(all_reason_codes))

        per_account.append(
            {
                "account_id": acc_id[:12] + "..." if len(acc_id) > 12 else acc_id,
                "account_id_full": acc_id,
                "risk_score": round(max_risk, 3),
                "mule_classification": mule_classification,
                "smurf_score": round(smurf_score, 3),
                "rule_hits": unique_reasons[:10],
                "alert_count": len(related_alerts),
                # CBS features
                "account_age_days": acc.get("account_age_days", 0),
                "debit_count": acc.get("debit_count", 0),
                "credit_count": acc.get("credit_count", 0),
                "debit_volume": acc.get("debit_volume", 0),
                "credit_volume": acc.get("credit_volume", 0),
                "pass_through_ratio": acc.get("pass_through_ratio", 0),
                "balance_volatility": acc.get("balance_volatility", 0),
                "negative_balance_count": acc.get("negative_balance_count", 0),
                "debit_credit_ratio": acc.get("debit_credit_ratio", 0),
                "max_single_txn_ratio": acc.get("max_single_txn_ratio", 0),
                # Node-level scores if available
                "betweenness": node_data.get("betweenness", 0),
                "pagerank": node_data.get("pagerank", 0),
                "baseline_deviation": node_data.get("baseline_deviation", 0),
            }
        )

    # Sort by risk score descending
    per_account.sort(key=lambda x: -x["risk_score"])

    # Aggregate statistics
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for alert in alerts:
        sev = alert.get("severity", "MEDIUM")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    classification_counts = {"COMPLICIT": 0, "EXPLOITED": 0, "CLEAN": 0}
    for pa in per_account:
        mc = pa["mule_classification"]
        classification_counts[mc] = classification_counts.get(mc, 0) + 1

    # Feature importance: count how often each reason code appears
    reason_counts: dict = defaultdict(int)
    for alert in alerts:
        for code in alert.get("reason_codes", []):
            reason_counts[code] += 1
    feature_importance = sorted(
        [{"signal": k, "count": v} for k, v in reason_counts.items()],
        key=lambda x: -x["count"],
    )

    # Cluster membership
    clusters = []
    for alert in alerts:
        cluster_members = [
            n.get("account_id", "") for n in alert.get("nodes", []) if n.get("account_id", "") in account_ids
        ]
        if cluster_members:
            clusters.append(
                {
                    "alert_id": alert.get("alert_id", ""),
                    "severity": alert.get("severity", ""),
                    "risk_score": alert.get("risk_score", 0),
                    "members": cluster_members,
                    "member_count": len(cluster_members),
                    "total_amount": alert.get("total_amount", 0),
                }
            )

    # Internal link stats
    internal_txns = sum(1 for t in transactions if t["from_account"] in account_ids and t["to_account"] in account_ids)

    return {
        "per_account": per_account,
        "aggregate": {
            "total_accounts": len(accounts),
            "total_transactions": len(transactions),
            "internal_links": internal_txns,
            "total_alerts": len(alerts),
            "mule_candidates": classification_counts["COMPLICIT"] + classification_counts["EXPLOITED"],
            "severity_counts": severity_counts,
            "classification_counts": classification_counts,
            "feature_importance": feature_importance[:15],
            "data_quality": dataset.get("data_quality", {}),
        },
        "clusters": clusters,
    }
