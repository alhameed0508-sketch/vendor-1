"""
MuleCatch Narrative Generator
===============================
Generates judge-ready, natural language narratives for alerts.

Three output modes:
  1. executive_brief   — 3-sentence summary for judges/CXOs
  2. detailed_narrative — full forensic walkthrough for investigators
  3. regulatory_summary — RBI/FIU-IND compliance language
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AlertNarrative:
    alert_id: str
    executive_brief: str
    detailed_narrative: str
    regulatory_summary: str
    key_findings: List[str]
    risk_factors: List[str]
    recommended_actions: List[str]
    mule_type: Optional[str]
    mule_type_reasoning: Optional[str]

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "executive_brief": self.executive_brief,
            "detailed_narrative": self.detailed_narrative,
            "regulatory_summary": self.regulatory_summary,
            "key_findings": self.key_findings,
            "risk_factors": self.risk_factors,
            "recommended_actions": self.recommended_actions,
            "mule_type": self.mule_type,
            "mule_type_reasoning": self.mule_type_reasoning,
        }


def _format_inr(amount: float) -> str:
    if amount >= 10_000_000:
        return f"\u20b9{amount / 10_000_000:.2f} Cr"
    if amount >= 100_000:
        return f"\u20b9{amount / 100_000:.2f} L"
    return f"\u20b9{amount:,.0f}"


def _severity_word(severity: str) -> str:
    return {
        "CRITICAL": "critical-severity",
        "HIGH": "high-severity",
        "MEDIUM": "medium-severity",
    }.get(severity, severity.lower())


def _count_roles(nodes: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for n in nodes:
        role = n.get("role", "UNKNOWN")
        counts[role] = counts.get(role, 0) + 1
    return counts


def generate_narrative(
    alert: Dict,
    mule_classification: Optional[Dict] = None,
) -> AlertNarrative:
    alert_id = alert.get("alert_id", "UNKNOWN")
    severity = alert.get("severity", "MEDIUM")
    risk_score = alert.get("risk_score", 0)
    total_amount = alert.get("total_amount", 0)
    account_count = alert.get("account_count", 0)
    txn_count = alert.get("txn_count", 0)
    nodes = alert.get("nodes", [])
    reason_codes = alert.get("reason_codes", [])
    shared_devices = alert.get("shared_devices", [])
    shared_ips = alert.get("shared_ips", [])
    gnn_score = alert.get("gnn_score")
    anomaly_score = alert.get("anomaly_score")
    explanation = alert.get("explanation", {})

    role_counts = _count_roles(nodes)
    mule_count = role_counts.get("MULE", 0)
    source_count = role_counts.get("SOURCE", 0)
    agg_count = role_counts.get("AGGREGATOR", 0)

    amount_str = _format_inr(total_amount)
    score_pct = round(risk_score * 100)

    mule_type = None
    mule_type_reasoning = None
    if mule_classification:
        mule_type = mule_classification.get("classification")
        mule_type_reasoning = mule_classification.get("reasoning")

    # ── Executive Brief ──
    device_clause = ""
    if shared_devices:
        device_clause = (
            f" Physical evidence shows {len(shared_devices)} device(s) "
            f"shared across accounts, confirming coordinated operation."
        )

    executive_brief = (
        f"MuleCatch has identified a {_severity_word(severity)} mule network "
        f"involving {account_count} accounts transacting {amount_str} across "
        f"{txn_count} transactions with a {score_pct}% risk score."
        f"{device_clause} "
        f"The network contains {source_count} source(s), {mule_count} mule layer(s), "
        f"and {agg_count} aggregation point(s)."
    )

    # ── Key Findings ──
    key_findings = []

    key_findings.append(
        f"Four-layer detection (Rules + Smurf-Weighting + Louvain + GNN) "
        f"produced a composite risk score of {score_pct}%"
    )

    if shared_devices:
        key_findings.append(
            f"{len(shared_devices)} device fingerprint(s) shared across multiple accounts "
            f"- strong indicator of single-operator control"
        )

    if shared_ips:
        key_findings.append(
            f"{len(shared_ips)} IP address(es) shared across accounts - accounts accessed from same physical location"
        )

    young_accounts = [n for n in nodes if n.get("account_age_days", 999) < 30]
    if young_accounts:
        key_findings.append(
            f"{len(young_accounts)} account(s) less than 30 days old - newly opened accounts used as mule conduits"
        )

    pending_kyc = [n for n in nodes if n.get("kyc_status") == "PENDING"]
    if pending_kyc:
        key_findings.append(f"{len(pending_kyc)} account(s) with incomplete KYC verification")

    if gnn_score is not None:
        key_findings.append(
            f"Graph Neural Network independently classified this cluster "
            f"as {round(gnn_score * 100)}% likely mule network"
        )

    if anomaly_score is not None:
        key_findings.append(
            "Label-free peer analysis independently identified an account at "
            f"{round(anomaly_score * 100)}% anomaly risk"
        )

    structuring_codes = [rc for rc in reason_codes if "threshold" in rc.lower() or "structur" in rc.lower()]
    if structuring_codes:
        key_findings.append("Transaction amounts deliberately structured below \u20b950,000 reporting threshold")

    # ── Risk Factors ──
    risk_factors = []
    for rc in reason_codes[:6]:
        code_parts = rc.split(": ", 1)
        if len(code_parts) == 2:
            risk_factors.append(f"[{code_parts[0]}] {code_parts[1]}")
        else:
            risk_factors.append(rc)

    # ── Detailed Narrative ──
    paragraphs = []

    paragraphs.append(
        f"ALERT {alert_id}: MuleCatch's four-layer detection pipeline has identified "
        f"a {_severity_word(severity)} suspicious cluster involving {account_count} accounts "
        f"that collectively processed {amount_str} across {txn_count} transactions. "
        f"The composite risk score is {score_pct}%, computed as a weighted blend of "
        f"Louvain community topology (50%), Smurf-weighting behavioral analysis (30%), "
        f"and GraphSAGE neural network classification (20%)."
    )

    if source_count or mule_count or agg_count:
        paragraphs.append(
            f"Network topology analysis reveals a classic mule network structure: "
            f"{source_count} source account(s) originating illicit funds, "
            f"{mule_count} intermediary mule account(s) used for layering, and "
            f"{agg_count} aggregator account(s) consolidating the proceeds. "
            f"This layered structure is designed so that funds "
            f"spiral through concentric layers to obscure their origin."
        )

    if shared_devices or shared_ips:
        evidence_parts = []
        if shared_devices:
            evidence_parts.append(f"{len(shared_devices)} shared device fingerprint(s)")
        if shared_ips:
            evidence_parts.append(f"{len(shared_ips)} shared IP address(es)")
        paragraphs.append(
            f"Physical evidence strengthens this assessment: {' and '.join(evidence_parts)} "
            f"link multiple accounts to the same operator. This type of digital forensic "
            f"evidence is admissible and significantly reduces false positive probability."
        )

    chain_narrative = explanation.get("chain_narrative", "")
    if chain_narrative:
        paragraphs.append(f"Money Flow Analysis: {chain_narrative}")

    cycle_narrative = explanation.get("cycle_narrative", "")
    if cycle_narrative and "No circular" not in cycle_narrative:
        paragraphs.append(f"Circular Flow Detection: {cycle_narrative}")

    if mule_type:
        paragraphs.append(
            f"Mule Classification: The accounts in this network are classified as "
            f"{mule_type}. {mule_type_reasoning or ''}"
        )

    detailed_narrative = "\n\n".join(paragraphs)

    # ── Regulatory Summary ──
    reg_parts = []
    reg_parts.append(
        "This Suspicious Transaction Report is generated pursuant to the "
        "Prevention of Money Laundering Act (PMLA) 2002 and RBI Master Directions "
        "on Fraud Risk Management (July 2024). The reporting entity is Indian Overseas Bank "
        "(IFSC: IOBA0000001)."
    )
    reg_parts.append(
        f"MuleCatch automated detection system identified {account_count} accounts "
        f"exhibiting mule account behavior patterns as defined by RBI Circular dated "
        f"January 2025 on Mule Account Prevention. Total suspicious transaction value: "
        f"{amount_str}. Detection confidence: {score_pct}%."
    )
    reg_parts.append(
        f"Detection methods employed: (1) 19-rule deterministic engine aligned with "
        f"RBIH MuleHunter.AI framework, (2) Smurf-weighting temporal analysis, "
        f"(3) Louvain graph community detection, (4) GraphSAGE neural network. "
        f"Reason codes triggered: {', '.join(rc.split(':')[0] for rc in reason_codes[:6])}."
    )
    reg_parts.append(
        "Recommended action: File STR with FIU-IND (FIU-IND v2.1 format) and "
        "initiate enhanced due diligence on all accounts in this cluster."
    )

    regulatory_summary = " ".join(reg_parts)

    # ── Recommended Actions ──
    recommended_actions = []
    if severity == "CRITICAL":
        recommended_actions.extend(
            [
                "IMMEDIATE: Freeze SOURCE and AGGREGATOR accounts",
                "File STR with FIU-IND within 24 hours",
                "Escalate to Chief Compliance Officer",
                "Preserve all transaction records and device logs",
                "Coordinate with cyber cell if organized fraud suspected",
            ]
        )
    elif severity == "HIGH":
        recommended_actions.extend(
            [
                "Place transaction hold on flagged accounts",
                "File STR with FIU-IND within 7 days",
                "Initiate enhanced due diligence on all cluster accounts",
                "Review and verify KYC documentation",
            ]
        )
    else:
        recommended_actions.extend(
            [
                "Monitor accounts for escalating activity",
                "Complete KYC verification for pending accounts",
                "Review transaction patterns weekly",
                "Consider STR filing if patterns persist",
            ]
        )

    return AlertNarrative(
        alert_id=alert_id,
        executive_brief=executive_brief,
        detailed_narrative=detailed_narrative,
        regulatory_summary=regulatory_summary,
        key_findings=key_findings,
        risk_factors=risk_factors,
        recommended_actions=recommended_actions,
        mule_type=mule_type,
        mule_type_reasoning=mule_type_reasoning,
    )
