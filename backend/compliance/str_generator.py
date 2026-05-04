"""
STR Generator
=============
Produces FIU-IND v2.1 compatible Suspicious Transaction Reports.
Output format aligns with RBI PMLA reporting requirements.
"""

import uuid
from datetime import datetime
from typing import List, Dict


REPORTING_ENTITY = "Indian Overseas Bank"
REPORTING_IFSC   = "IOBA0000001"
FIU_FORMAT       = "2.1"


def generate_str(alert: Dict) -> Dict:
    """Generate a single STR from a MuleCatch alert"""
    accounts = [n["account_id"] for n in alert.get("nodes", [])]
    patterns = list({e.get("pattern", "") for e in alert.get("edges", [])
                     if e.get("pattern") not in (None, "NORMAL")})

    return {
        "str_id":                  f"STR_{uuid.uuid4().hex[:8].upper()}",
        "fiu_format_version":      FIU_FORMAT,
        "reporting_entity":        REPORTING_ENTITY,
        "reporting_branch_ifsc":   REPORTING_IFSC,
        "report_date":             datetime.utcnow().date().isoformat(),
        "alert_reference":         alert["alert_id"],
        "cluster_reference":       alert.get("cluster_id", ""),
        "transaction_type":        "UPI/NEFT",
        "suspicion_indicators":    alert.get("reason_codes", []),
        "fraud_patterns_detected": patterns,
        "total_amount_inr":        alert["total_amount"],
        "transaction_count":       alert["txn_count"],
        "accounts_involved":       accounts,
        "shared_devices":          alert.get("shared_devices", []),
        "shared_ips":              alert.get("shared_ips", []),
        "risk_score":              alert["risk_score"],
        "confidence":              alert.get("confidence", 0),
        "network_topology_method": "Louvain Community Detection + Smurf-Weighting",
        "detection_system":        "MuleCatch v1.0",
        "graph_evidence":          "Subgraph attached via alert reference",
        "investigator_notes":      alert.get("investigator_notes", ""),
        "status":                  "READY_FOR_SUBMISSION",
        "generated_at":            datetime.utcnow().isoformat(),
        "audit_trail_ref":         f"AUD_{uuid.uuid4().hex[:8].upper()}",
    }


def generate_batch_str(alerts: List[Dict]) -> List[Dict]:
    return [generate_str(a) for a in alerts]