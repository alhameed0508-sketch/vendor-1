"""
GenAI Service — orchestrates LLM-powered capabilities for MuleCatch.

Three capabilities:
1. Alert forensic analysis (executive brief / detailed narrative / regulatory)
2. Investigation assistant (conversational Q&A — "Ask MuleCatch")
3. Onboarding risk explanation (plain-English signal interpretation)

Falls back to template-based narratives when no LLM is available.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from genai.base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# ── System prompts with Indian AML regulatory context ───────────────────────

SYSTEM_PROMPT_FORENSIC = """You are MuleCatch AI, an expert anti-money laundering forensic analyst
deployed at Indian Overseas Bank. You analyze mule account network alerts.

Regulatory context:
- PMLA 2002 (Prevention of Money Laundering Act)
- RBI Circular January 2025 on Mule Account Prevention
- RBI Master Directions on Fraud Risk Management (July 2024)
- FIU-IND STR v2.1 reporting format
- RBIH MuleHunter.AI framework (19 behavioral rules)

Your analysis must include:
1. Executive Brief (3 sentences for CXOs/judges)
2. Detailed Narrative (forensic walkthrough for investigators)
3. Regulatory Summary (PMLA/RBI compliance language)
4. Key Findings (bullet points)
5. Recommended Actions (prioritized)

Use INR formatting (₹). Reference specific detection layers that fired.
Be precise, factual, and cite relevant regulations."""

SYSTEM_PROMPT_CHAT = """You are MuleCatch AI, an investigation assistant for anti-money laundering
analysts at Indian Overseas Bank.

You help investigators understand alerts, mule network patterns, and
Indian AML regulations. You can explain:
- Why specific accounts were flagged
- How the 4-layer detection works (Rules + Smurf-Weighting + Louvain + GNN)
- RBI/PMLA regulatory requirements
- Transaction pattern analysis
- Network topology interpretation

Be concise, factual, and helpful. Reference Indian regulations when relevant.
If you don't know something, say so clearly."""

SYSTEM_PROMPT_ONBOARDING = """You are MuleCatch AI, explaining onboarding risk assessment results
for Indian Overseas Bank's account opening process.

Explain in plain English why an account application was flagged as risky.
The 14-signal scoring engine evaluates:
1. Account age (days)
2. KYC completeness (0-1)
3. Document verification speed (seconds)
4. Device overlap with existing accounts
5. IP geolocation mismatch
6. Phone number age (days)
7. Email age (days)
8. Address verification status
9. Selfie confidence score
10. Application velocity (multiple apps)
11. Similar name matches
12. High-risk geography flag
13. Application hour (off-hours)
14. Behavioral pattern consistency

Reference RBI KYC Master Directions and PMLA Section 12 where relevant.
Explain which signals fired and why they indicate potential mule risk."""

SYSTEM_PROMPT_TRIAGE = """You are MuleCatch AI, a fraud detection triage analyst at Indian Overseas Bank.
Given transaction network cluster data, assess the likelihood that this cluster
represents a mule account network.

Consider:
- Account ages (newer = more suspicious for mule patterns)
- Transaction patterns (smurfing, consolidation, structuring)
- Device/IP sharing (legitimate family sharing vs coordinated fraud)
- KYC status (pending KYC with high volume = red flag)
- Transaction velocity and amounts relative to account history
- Number of unique recipients/senders

Respond with EXACTLY this JSON format (no markdown, no extra text):
{"assessment": "HIGH" or "MEDIUM" or "LOW", "reasoning": "<2-3 sentences>"}

- HIGH: Strong indicators of coordinated mule network activity
- MEDIUM: Inconclusive — some suspicious signals but also legitimate explanations
- LOW: Likely legitimate activity that triggered false positive rules"""

SYSTEM_PROMPT_PATTERN_DISCOVERY = """You are MuleCatch AI, analyzing financial transactions for novel
mule account patterns not covered by standard detection rules.

Focus on:
- Emerging patterns in Indian digital payments (UPI, IMPS, NEFT)
- New money laundering techniques targeting RBI reporting thresholds
- Behavioral patterns that evade the 19 MuleHunter.AI rules
- Cross-institution layering via UPI interoperability
- Social engineering / money mule recruitment indicators

Return EXACTLY this JSON format (no markdown, no extra text):
{
  "patterns": [
    {"name": "<pattern_name>", "description": "<what_it_detects>", "risk_level": "HIGH/MEDIUM/LOW"}
  ],
  "risk_indicators": ["<indicator_1>", "<indicator_2>"],
  "novel_signals": ["<signal_1>", "<signal_2>"]
}"""


@dataclass(frozen=True)
class TriageResult:
    """Immutable result from LLM triage of a cluster."""
    cluster_id: str
    llm_assessment: str        # "HIGH" | "MEDIUM" | "LOW"
    confidence_adjustment: float  # -0.10 to +0.10
    reasoning: str
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "cluster_id": self.cluster_id,
            "llm_assessment": self.llm_assessment,
            "confidence_adjustment": self.confidence_adjustment,
            "reasoning": self.reasoning,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class PatternDiscovery:
    """Immutable result from LLM pattern discovery."""
    suggested_patterns: List[Dict]
    risk_indicators: List[str]
    novel_signals: List[str]
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "suggested_patterns": self.suggested_patterns,
            "risk_indicators": self.risk_indicators,
            "novel_signals": self.novel_signals,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class ForensicAnalysis:
    """Immutable result from LLM forensic analysis."""
    alert_id: str
    executive_brief: str
    detailed_narrative: str
    regulatory_summary: str
    key_findings: List[str]
    recommended_actions: List[str]
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "executive_brief": self.executive_brief,
            "detailed_narrative": self.detailed_narrative,
            "regulatory_summary": self.regulatory_summary,
            "key_findings": self.key_findings,
            "recommended_actions": self.recommended_actions,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


@dataclass(frozen=True)
class ChatResponse:
    """Immutable chat response."""
    message: str
    provider: str
    model: str
    latency_ms: float
    is_llm_generated: bool

    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "is_llm_generated": self.is_llm_generated,
        }


class GenAIService:
    """Orchestrates GenAI capabilities with template fallback."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider
        self._is_real_llm = (
            provider is not None
            and provider.provider_name != "template_fallback"
        )

    @property
    def is_enabled(self) -> bool:
        return self._is_real_llm

    @property
    def provider_name(self) -> str:
        if self._provider is None:
            return "none"
        return self._provider.provider_name

    def get_status(self) -> Dict:
        """Return current GenAI status for the status endpoint."""
        return {
            "enabled": self._is_real_llm,
            "provider": self.provider_name,
            "fallback_active": not self._is_real_llm,
        }

    # ── 1. Forensic Analysis ──────────────────────────────────────────────

    def analyze_alert(self, alert_data: Dict) -> ForensicAnalysis:
        """
        Generate LLM forensic analysis for an alert.
        Falls back to template narrative if LLM unavailable.
        """
        alert_id = alert_data.get("alert_id", "UNKNOWN")

        if not self._is_real_llm:
            return self._template_forensic(alert_data)

        prompt = self._build_forensic_prompt(alert_data)

        try:
            response = self._provider.generate(
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT_FORENSIC),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            return self._parse_forensic_response(
                alert_id, response
            )
        except Exception as exc:
            logger.error("LLM forensic analysis failed for %s: %s", alert_id, exc)
            return self._template_forensic(alert_data)

    def _build_forensic_prompt(self, alert: Dict) -> str:
        """Build the forensic analysis prompt from alert data."""
        nodes = alert.get("nodes", [])
        edges = alert.get("edges", [])
        reason_codes = alert.get("reason_codes", [])

        node_summary = []
        for n in nodes[:15]:
            node_summary.append(
                f"  - {n.get('account_id')}: role={n.get('role')}, "
                f"smurf_score={n.get('smurf_score', 0):.2f}, "
                f"bank={n.get('bank')}, city={n.get('city')}, "
                f"age={n.get('account_age_days')}d, kyc={n.get('kyc_status')}"
            )

        edge_summary = []
        for e in edges[:20]:
            edge_summary.append(
                f"  - {e.get('from_account')} -> {e.get('to_account')}: "
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

    def _parse_forensic_response(
        self, alert_id: str, response: LLMResponse
    ) -> ForensicAnalysis:
        """Parse LLM response into structured ForensicAnalysis."""
        text = response.content
        sections = {
            "executive_brief": "",
            "detailed_narrative": "",
            "regulatory_summary": "",
        }
        key_findings = []
        recommended_actions = []

        current_section = None
        current_lines = []

        for line in text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            if "executive brief" in lower and stripped.startswith("#"):
                if current_section:
                    self._store_section(
                        current_section, current_lines, sections,
                        key_findings, recommended_actions,
                    )
                current_section = "executive_brief"
                current_lines = []
            elif "detailed narrative" in lower and stripped.startswith("#"):
                if current_section:
                    self._store_section(
                        current_section, current_lines, sections,
                        key_findings, recommended_actions,
                    )
                current_section = "detailed_narrative"
                current_lines = []
            elif "regulatory summary" in lower and stripped.startswith("#"):
                if current_section:
                    self._store_section(
                        current_section, current_lines, sections,
                        key_findings, recommended_actions,
                    )
                current_section = "regulatory_summary"
                current_lines = []
            elif "key findings" in lower and stripped.startswith("#"):
                if current_section:
                    self._store_section(
                        current_section, current_lines, sections,
                        key_findings, recommended_actions,
                    )
                current_section = "key_findings"
                current_lines = []
            elif "recommended actions" in lower and stripped.startswith("#"):
                if current_section:
                    self._store_section(
                        current_section, current_lines, sections,
                        key_findings, recommended_actions,
                    )
                current_section = "recommended_actions"
                current_lines = []
            else:
                current_lines.append(line)

        # Store final section
        if current_section:
            self._store_section(
                current_section, current_lines, sections,
                key_findings, recommended_actions,
            )

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

    @staticmethod
    def _store_section(
        section_name: str,
        lines: List[str],
        sections: Dict,
        key_findings: List[str],
        recommended_actions: List[str],
    ) -> None:
        text = "\n".join(lines).strip()
        if section_name in ("key_findings",):
            for line in lines:
                stripped = line.strip().lstrip("-*• ")
                if stripped:
                    key_findings.append(stripped)
        elif section_name in ("recommended_actions",):
            for line in lines:
                stripped = line.strip().lstrip("-*•0123456789. ")
                if stripped:
                    recommended_actions.append(stripped)
        else:
            sections[section_name] = text

    def _template_forensic(self, alert_data: Dict) -> ForensicAnalysis:
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

    # ── 2. Investigation Chat ─────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        alert_context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> ChatResponse:
        """
        Investigation assistant chat.
        Falls back to a helpful static response if LLM unavailable.
        """
        if not self._is_real_llm:
            return ChatResponse(
                message=(
                    "GenAI is not configured. Set GENAI_ENABLED=true and provide "
                    "an API key to enable the investigation assistant. "
                    "You can still use the template-based narratives and "
                    "explainability panels for alert analysis."
                ),
                provider="template_fallback",
                model="template",
                latency_ms=0.0,
                is_llm_generated=False,
            )

        messages = [LLMMessage(role="system", content=SYSTEM_PROMPT_CHAT)]

        # Add alert context if provided
        if alert_context:
            context_str = self._format_alert_context(alert_context)
            messages.append(LLMMessage(
                role="system",
                content=f"Current alert context:\n{context_str}",
            ))

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-10:]:  # Keep last 10 messages
                role = msg.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append(LLMMessage(role=role, content=msg["content"]))

        messages.append(LLMMessage(role="user", content=user_message))

        try:
            response = self._provider.generate(
                messages=messages,
                temperature=0.4,
                max_tokens=1024,
            )
            return ChatResponse(
                message=response.content,
                provider=response.provider,
                model=response.model,
                latency_ms=response.latency_ms,
                is_llm_generated=True,
            )
        except Exception as exc:
            logger.error("LLM chat failed: %s", exc)
            return ChatResponse(
                message=f"I encountered an error processing your request. Please try again.",
                provider="error",
                model="none",
                latency_ms=0.0,
                is_llm_generated=False,
            )

    @staticmethod
    def _format_alert_context(alert: Dict) -> str:
        """Format alert data for chat context injection."""
        return (
            f"Alert: {alert.get('alert_id', 'N/A')}\n"
            f"Severity: {alert.get('severity', 'N/A')}\n"
            f"Risk Score: {alert.get('risk_score', 0):.3f}\n"
            f"Accounts: {alert.get('account_count', 0)}\n"
            f"Total Amount: ₹{alert.get('total_amount', 0):,.0f}\n"
            f"Reason Codes: {', '.join(alert.get('reason_codes', [])[:5])}"
        )

    def get_suggested_questions(self, alert_data: Optional[Dict] = None) -> List[str]:
        """Return suggested questions based on alert context."""
        base_questions = [
            "What does the risk score mean for this alert?",
            "Explain the mule network structure in this cluster.",
            "What RBI regulations apply to this suspicious activity?",
            "What should I do as the next investigation step?",
            "How confident is MuleCatch in this detection?",
        ]
        if alert_data:
            severity = alert_data.get("severity", "")
            if severity == "CRITICAL":
                base_questions[0] = "Why is this alert classified as CRITICAL?"
            reason_codes = alert_data.get("reason_codes", [])
            if reason_codes:
                first_code = reason_codes[0].split(":")[0] if ":" in reason_codes[0] else reason_codes[0]
                base_questions[1] = f"Explain rule {first_code} — why did it trigger?"
        return base_questions

    # ── 3. Onboarding Risk Explanation ────────────────────────────────────

    def explain_onboarding(self, assessment: Dict) -> ChatResponse:
        """
        Generate plain-English explanation of onboarding risk assessment.
        Falls back to a structured template explanation.
        """
        if not self._is_real_llm:
            return self._template_onboarding_explanation(assessment)

        prompt = self._build_onboarding_prompt(assessment)

        try:
            response = self._provider.generate(
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT_ONBOARDING),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return ChatResponse(
                message=response.content,
                provider=response.provider,
                model=response.model,
                latency_ms=response.latency_ms,
                is_llm_generated=True,
            )
        except Exception as exc:
            logger.error("LLM onboarding explanation failed: %s", exc)
            return self._template_onboarding_explanation(assessment)

    def _build_onboarding_prompt(self, assessment: Dict) -> str:
        signals = assessment.get("signals", [])
        signal_lines = []
        for sig in signals:
            signal_lines.append(
                f"  - {sig.get('signal', 'unknown')}: "
                f"score={sig.get('score', 0):.2f}, "
                f"weight={sig.get('weight', 0)}, "
                f"weighted={sig.get('weighted', 0):.4f}"
            )
        reason_codes = assessment.get("reason_codes", [])
        return f"""Explain this onboarding risk assessment in plain English:

Account: {assessment.get('account_id', 'N/A')}
Risk Score: {assessment.get('risk_score', 0):.2f}
Risk Level: {assessment.get('risk_level', 'N/A')}
Recommendation: {assessment.get('recommendation', 'N/A')}

Triggered Reason Codes:
{chr(10).join(f'  - {rc}' for rc in reason_codes)}

Signal Breakdown:
{chr(10).join(signal_lines)}

Explain which signals contributed most to the risk score, what they mean
in practical terms, and what the bank should do next."""

    @staticmethod
    def _template_onboarding_explanation(assessment: Dict) -> ChatResponse:
        """Template-based onboarding explanation."""
        risk_level = assessment.get("risk_level", "UNKNOWN")
        risk_score = assessment.get("risk_score", 0)
        reason_codes = assessment.get("reason_codes", [])
        signals = assessment.get("signals", [])

        # Sort signals by weighted score descending
        top_signals = sorted(
            signals, key=lambda s: s.get("weighted", 0), reverse=True
        )[:5]

        lines = [
            f"Risk Assessment: {risk_level} ({risk_score:.0%} risk score)",
            "",
        ]

        if reason_codes:
            lines.append("Flags triggered:")
            for rc in reason_codes:
                lines.append(f"  - {rc}")
            lines.append("")

        if top_signals:
            lines.append("Top contributing signals:")
            for sig in top_signals:
                name = sig.get("signal", "").replace("_", " ").title()
                score = sig.get("score", 0)
                lines.append(f"  - {name}: {score:.2f}")
            lines.append("")

        lines.append(
            f"Recommendation: {assessment.get('recommendation', 'Review manually')}"
        )

        return ChatResponse(
            message="\n".join(lines),
            provider="template_fallback",
            model="template",
            latency_ms=0.0,
            is_llm_generated=False,
        )

    # ── 4. Cluster Triage ────────────────────────────────────────────────

    _ASSESSMENT_ADJUSTMENTS = {
        "HIGH": 0.10,
        "MEDIUM": 0.00,
        "LOW": -0.10,
    }

    def triage_cluster(self, alert_data: Dict) -> TriageResult:
        """
        LLM triage of a suspicious cluster. Returns assessment with
        confidence adjustment. Falls back to MEDIUM / 0.00 when no LLM.
        """
        cluster_id = alert_data.get("cluster_id", "UNKNOWN")

        if not self._is_real_llm:
            return self._template_triage(alert_data)

        prompt = self._build_triage_prompt(alert_data)
        start_ms = time.perf_counter() * 1000

        try:
            response = self._provider.generate(
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT_TRIAGE),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.2,
                max_tokens=512,
            )
            latency = time.perf_counter() * 1000 - start_ms
            return self._parse_triage_response(
                cluster_id, response, latency,
            )
        except Exception as exc:
            logger.error("LLM triage failed for %s: %s", cluster_id, exc)
            return self._template_triage(alert_data)

    def _build_triage_prompt(self, alert: Dict) -> str:
        nodes = alert.get("nodes", [])
        edges = alert.get("edges", [])

        node_lines = []
        for n in nodes[:15]:
            node_lines.append(
                f"  - {n.get('account_id')}: role={n.get('role')}, "
                f"smurf={n.get('smurf_score', 0):.2f}, "
                f"age={n.get('account_age_days')}d, kyc={n.get('kyc_status')}"
            )

        edge_lines = []
        for e in edges[:20]:
            edge_lines.append(
                f"  - {e.get('from_account')} -> {e.get('to_account')}: "
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
        self, cluster_id: str, response: LLMResponse, latency_ms: float,
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

        if assessment not in self._ASSESSMENT_ADJUSTMENTS:
            assessment = "MEDIUM"

        return TriageResult(
            cluster_id=cluster_id,
            llm_assessment=assessment,
            confidence_adjustment=self._ASSESSMENT_ADJUSTMENTS[assessment],
            reasoning=reasoning,
            provider=response.provider,
            model=response.model,
            latency_ms=latency_ms,
            is_llm_generated=True,
        )

    @staticmethod
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

    # ── 5. Pattern Discovery ─────────────────────────────────────────────

    def discover_patterns(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> PatternDiscovery:
        """
        LLM-powered discovery of novel mule patterns in a batch of data.
        Falls back to empty pattern list when no LLM available.
        """
        if not self._is_real_llm:
            return self._template_pattern_discovery()

        prompt = self._build_pattern_prompt(transactions, accounts)
        start_ms = time.perf_counter() * 1000

        try:
            response = self._provider.generate(
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT_PATTERN_DISCOVERY),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            latency = time.perf_counter() * 1000 - start_ms
            return self._parse_pattern_response(response, latency)
        except Exception as exc:
            logger.error("LLM pattern discovery failed: %s", exc)
            return self._template_pattern_discovery()

    def _build_pattern_prompt(
        self, transactions: List[Dict], accounts: List[Dict],
    ) -> str:
        # Summarize rather than send raw data
        total_txns = len(transactions)
        total_accounts = len(accounts)
        roles = {}
        for a in accounts:
            role = a.get("role", "UNKNOWN")
            roles[role] = roles.get(role, 0) + 1

        amounts = [float(t["amount"]) for t in transactions]
        avg_amount = sum(amounts) / max(len(amounts), 1)
        max_amount = max(amounts) if amounts else 0

        patterns = {}
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
    f"  {t['from_account']} -> {t['to_account']}: ₹{float(t['amount']):,.0f} ({t.get('pattern', 'N/A')})"
    for t in transactions[:20]
)}

Identify novel patterns, risk indicators, and signals not covered
by standard MuleHunter.AI rules (R01-R20)."""

    def _parse_pattern_response(
        self, response: LLMResponse, latency_ms: float,
    ) -> PatternDiscovery:
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

    @staticmethod
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
