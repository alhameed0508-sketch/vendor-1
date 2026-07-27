"""
Narrative Agent — auto-generates FIU-IND compliant STR narratives
from assembled case files.

Uses LLM when available, falls back to structured template generation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List

from services.investigation.case_assembler import CaseFile

logger = logging.getLogger(__name__)


def _mask_account(account_id: str) -> str:
    """Hash-based masking for account IDs in narratives."""
    if not account_id:
        return "N/A"
    return f"ACCT_{hashlib.sha256(account_id.encode()).hexdigest()[:8]}"


SYSTEM_PROMPT_STR = """You are MuleCatch AI, generating FIU-IND compliant STR (Suspicious Transaction Report)
narratives for Indian Overseas Bank.

You must produce a structured narrative with these exact sections:
1. Subject Information — masked account identifiers, cluster info, account ages
2. Suspicious Activity Description — risk assessment, severity, key indicators
3. Transaction Details — amounts, patterns, timeline, counterparties
4. Supporting Evidence — device sharing, behavioral deviations, network topology
5. Conclusion — recommended actions, regulatory references (PMLA 2002, RBI circulars)

IMPORTANT:
- NEVER include raw account numbers — always use masked identifiers
- Use INR (₹) formatting for amounts
- Reference PMLA 2002, RBI Master Directions on Fraud Risk Management
- Be precise, factual, and concise"""


@dataclass(frozen=True)
class STRNarrative:
    """Immutable FIU-IND compliant STR narrative."""

    alert_id: str
    subject_info: str
    activity_description: str
    transaction_details: str
    supporting_evidence: str
    conclusion: str
    full_narrative: str
    is_llm_generated: bool
    provider: str

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "subject_info": self.subject_info,
            "activity_description": self.activity_description,
            "transaction_details": self.transaction_details,
            "supporting_evidence": self.supporting_evidence,
            "conclusion": self.conclusion,
            "full_narrative": self.full_narrative,
            "is_llm_generated": self.is_llm_generated,
            "provider": self.provider,
        }


class NarrativeAgent:
    """Generates FIU-IND compliant STR narratives from case files."""

    def __init__(self, genai_service=None):
        self._genai = genai_service

    def generate_str_narrative(self, case_file: CaseFile) -> STRNarrative:
        """Generate FIU-IND compliant STR narrative from a case file.

        Uses LLM when available, otherwise falls back to template.
        """
        if self._genai is not None and self._genai.is_enabled:
            return self._llm_narrative(case_file)
        return self._template_narrative(case_file)

    def validate_narrative(self, narrative: STRNarrative) -> Dict:
        """Validate that narrative has all required fields and no PII leakage.

        Returns: {"valid": bool, "issues": list[str]}
        """
        issues: List[str] = []

        # Check all sections are non-empty
        for section_name in (
            "subject_info",
            "activity_description",
            "transaction_details",
            "supporting_evidence",
            "conclusion",
        ):
            value = getattr(narrative, section_name, "")
            if not value or not value.strip():
                issues.append(f"Empty section: {section_name}")

        if not narrative.full_narrative or not narrative.full_narrative.strip():
            issues.append("Empty full_narrative")

        # Check for raw account IDs (pattern: AC followed by digits)
        full_text = narrative.full_narrative
        self._check_pii_leakage(full_text, issues)

        return {"valid": len(issues) == 0, "issues": issues}

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _check_pii_leakage(text: str, issues: List[str]) -> None:
        """Check for un-masked account IDs in narrative text."""
        import re

        # Pattern: AC followed by 6+ digits (raw account IDs)
        raw_ids = re.findall(r"\bAC\d{6,}\b", text)
        for raw_id in raw_ids:
            issues.append(f"Raw account ID leaked: {raw_id}")

    def _llm_narrative(self, case_file: CaseFile) -> STRNarrative:
        """Generate narrative using LLM."""
        from genai.base import LLMMessage

        prompt = self._build_llm_prompt(case_file)
        try:
            response = self._genai._provider.generate(
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT_STR),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            return self._parse_llm_response(case_file.alert_id, response)
        except Exception as exc:
            logger.error("LLM narrative generation failed: %s", exc)
            return self._template_narrative(case_file)

    def _build_llm_prompt(self, case_file: CaseFile) -> str:
        """Build a structured prompt from case file data."""
        masked_ids = [_mask_account(aid) for aid in case_file.account_ids]
        evidence_lines = []
        for ev in case_file.evidence_items:
            evidence_lines.append(
                f"  - [{ev.severity}] {ev.evidence_type}: {ev.description}"
            )

        return f"""Generate an FIU-IND compliant STR narrative for this case:

Alert: {case_file.alert_id}
Case Strength: {case_file.case_strength}
Accounts: {", ".join(masked_ids)}
Total Amount: INR {case_file.transaction_summary.get("total_amount", 0):,.0f}
Transaction Count: {case_file.transaction_summary.get("txn_count", 0)}
Shared Devices: {case_file.graph_context.get("shared_device_count", 0)}
Shared IPs: {case_file.graph_context.get("shared_ip_count", 0)}

Evidence:
{chr(10).join(evidence_lines)}

Generate sections: Subject Information, Suspicious Activity Description,
Transaction Details, Supporting Evidence, Conclusion."""

    def _parse_llm_response(
        self,
        alert_id: str,
        response,
    ) -> STRNarrative:
        """Parse LLM response into structured STRNarrative."""
        text = response.content
        sections = {
            "subject_info": "",
            "activity_description": "",
            "transaction_details": "",
            "supporting_evidence": "",
            "conclusion": "",
        }
        section_map = {
            "subject information": "subject_info",
            "suspicious activity": "activity_description",
            "transaction details": "transaction_details",
            "supporting evidence": "supporting_evidence",
            "conclusion": "conclusion",
        }

        current_key = None
        current_lines: List[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            matched_key = None
            if stripped.startswith("#"):
                for trigger, key in section_map.items():
                    if trigger in lower:
                        matched_key = key
                        break

            if matched_key is not None:
                if current_key is not None:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = matched_key
                current_lines = []
            else:
                current_lines.append(line)

        if current_key is not None:
            sections[current_key] = "\n".join(current_lines).strip()

        # Fallback if parsing got nothing
        if not any(sections.values()):
            sections["activity_description"] = text

        full_narrative = "\n\n".join(
            f"## {name.replace('_', ' ').title()}\n{body}"
            for name, body in sections.items()
            if body
        )

        return STRNarrative(
            alert_id=alert_id,
            subject_info=sections["subject_info"],
            activity_description=sections["activity_description"],
            transaction_details=sections["transaction_details"],
            supporting_evidence=sections["supporting_evidence"],
            conclusion=sections["conclusion"],
            full_narrative=full_narrative,
            is_llm_generated=True,
            provider=response.provider,
        )

    @staticmethod
    def _template_narrative(case_file: CaseFile) -> STRNarrative:
        """Generate template-based STR narrative (fallback)."""
        masked_ids = [_mask_account(aid) for aid in case_file.account_ids]
        total_amount = case_file.transaction_summary.get("total_amount", 0)
        txn_count = case_file.transaction_summary.get("txn_count", 0)
        device_count = case_file.graph_context.get("shared_device_count", 0)
        ip_count = case_file.graph_context.get("shared_ip_count", 0)
        dev_count = case_file.behavioral_profile.get("deviation_count", 0)
        rules = case_file.screening_results.get("rule_triggers", [])
        top_cp = case_file.transaction_summary.get("top_counterparties", [])

        # Subject Information
        subject_info = (
            f"Subject accounts: {', '.join(masked_ids[:5])}. "
            f"Cluster of {len(case_file.account_ids)} account(s) flagged by "
            f"automated detection."
        )

        # Activity Description
        severity = (
            "CRITICAL"
            if case_file.case_strength == "STRONG"
            else ("HIGH" if case_file.case_strength == "MODERATE" else "MEDIUM")
        )
        rule_summary = (
            "; ".join(rules[:3]) if rules else "Multiple detection rules triggered"
        )
        activity_description = (
            f"Severity: {severity}. Case strength: {case_file.case_strength}. "
            f"Key indicators: {rule_summary}."
        )

        # Transaction Details
        cp_lines = ", ".join(
            f"{_mask_account(cp['account'])} (INR {cp['amount']:,.0f})"
            for cp in top_cp[:3]
        )
        date_range = case_file.transaction_summary.get("date_range", {})
        transaction_details = (
            f"Total amount: INR {total_amount:,.0f} across {txn_count} transaction(s). "
            f"Date range: {date_range.get('from', 'N/A')} to {date_range.get('to', 'N/A')}. "
            f"Top counterparties: {cp_lines or 'N/A'}."
        )

        # Supporting Evidence
        evidence_lines = []
        if device_count > 0:
            evidence_lines.append(f"{device_count} shared device(s)")
        if ip_count > 0:
            evidence_lines.append(f"{ip_count} shared IP(s)")
        if dev_count > 0:
            evidence_lines.append(f"{dev_count} behavioral deviation(s)")
        gnn = case_file.behavioral_profile.get("gnn_score")
        if gnn is not None:
            evidence_lines.append(f"GNN anomaly score: {gnn}")
        supporting_evidence = (
            "Supporting indicators: " + "; ".join(evidence_lines)
            if evidence_lines
            else "No additional supporting evidence."
        )

        # Conclusion
        if case_file.case_strength == "STRONG":
            action = (
                "Recommend immediate account freeze and STR filing with FIU-IND "
                "per PMLA 2002 Section 12. Escalate to compliance officer."
            )
        elif case_file.case_strength == "MODERATE":
            action = (
                "Recommend enhanced monitoring and investigation. "
                "Consider STR filing based on investigator review. "
                "Reference RBI Master Directions on Fraud Risk Management."
            )
        else:
            action = (
                "Recommend routine investigation review. "
                "Monitor for additional suspicious activity."
            )
        conclusion = action

        full_narrative = (
            f"## Subject Information\n{subject_info}\n\n"
            f"## Suspicious Activity Description\n{activity_description}\n\n"
            f"## Transaction Details\n{transaction_details}\n\n"
            f"## Supporting Evidence\n{supporting_evidence}\n\n"
            f"## Conclusion\n{conclusion}"
        )

        return STRNarrative(
            alert_id=case_file.alert_id,
            subject_info=subject_info,
            activity_description=activity_description,
            transaction_details=transaction_details,
            supporting_evidence=supporting_evidence,
            conclusion=conclusion,
            full_narrative=full_narrative,
            is_llm_generated=False,
            provider="template_fallback",
        )
