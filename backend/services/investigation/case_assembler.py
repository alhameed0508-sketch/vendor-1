"""
Case Assembly Agent — gathers all relevant evidence for an alert into
a structured, immutable case file for investigation and STR filing.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# -- Behavioral profile thresholds ---------------------------------------------
# Account younger than this (days) is flagged as new
THRESHOLD_YOUNG_ACCOUNT_DAYS = 7
# Smurf score above this triggers a behavioral flag
THRESHOLD_HIGH_SMURF_SCORE = 0.5
# Betweenness centrality above this indicates high graph centrality
THRESHOLD_HIGH_BETWEENNESS = 0.3
# Smurf score above this classifies evidence severity as HIGH
THRESHOLD_HIGH_SEVERITY_SMURF = 0.7


@dataclass(frozen=True)
class EvidenceItem:
    """Single piece of evidence contributing to a case."""

    evidence_type: str  # "transaction", "graph", "behavioral", "device", "screening", "onboarding", "typology"
    description: str
    data: Dict
    severity: str  # "HIGH", "MEDIUM", "LOW"


@dataclass(frozen=True)
class CaseFile:
    """Immutable, assembled case file for a single alert."""

    alert_id: str
    account_ids: Tuple[str, ...]
    transaction_summary: Dict
    graph_context: Dict
    behavioral_profile: Dict
    screening_results: Dict
    typology: Optional[Dict]
    timeline: Tuple[Dict, ...]
    evidence_items: Tuple[EvidenceItem, ...]
    created_at: str
    case_strength: str  # "STRONG", "MODERATE", "WEAK"


class CaseAssemblyAgent:
    """Assembles comprehensive case files from alert data."""

    def __init__(self, persistence=None, genai_service=None):
        self._persistence = persistence
        self._genai_service = genai_service

    def assemble_case(
        self,
        alert_id: str,
        alert_data: Dict,
        transactions: Optional[List[Dict]] = None,
        accounts: Optional[List[Dict]] = None,
    ) -> CaseFile:
        """Assemble a complete case file from all available evidence."""
        transactions = transactions or []
        accounts = accounts or []

        account_ids = self._extract_account_ids(alert_data, accounts)
        transaction_summary = self._build_transaction_summary(alert_data, transactions)
        graph_context = self._build_graph_context(alert_data)
        behavioral_profile = self._build_behavioral_profile(alert_data)
        screening_results = self._extract_screening_results(alert_data)
        typology = self._extract_typology(alert_data)
        timeline = self._build_timeline(alert_data, transactions)
        evidence_items = self._classify_evidence(
            alert_data,
            transaction_summary,
            graph_context,
            behavioral_profile,
            screening_results,
        )
        case_strength = self._assess_case_strength(evidence_items)

        return CaseFile(
            alert_id=alert_id,
            account_ids=tuple(account_ids),
            transaction_summary=transaction_summary,
            graph_context=graph_context,
            behavioral_profile=behavioral_profile,
            screening_results=screening_results,
            typology=typology,
            timeline=tuple(timeline),
            evidence_items=tuple(evidence_items),
            created_at=datetime.now(timezone.utc).isoformat(),
            case_strength=case_strength,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_account_ids(alert_data: Dict, accounts: List[Dict]) -> List[str]:
        """Collect unique account IDs from nodes and account list."""
        ids: List[str] = []
        for node in alert_data.get("nodes", []):
            aid = node.get("account_id")
            if aid and aid not in ids:
                ids.append(aid)
        for acct in accounts:
            aid = acct.get("account_id")
            if aid and aid not in ids:
                ids.append(aid)
        return ids

    @staticmethod
    def _build_transaction_summary(
        alert_data: Dict,
        transactions: List[Dict],
    ) -> Dict:
        """Summarize transaction amounts, count, date range, counterparties."""
        total_amount = alert_data.get("total_amount", 0.0)
        txn_count = alert_data.get("txn_count", 0)

        counterparties: Dict[str, float] = {}
        min_date: Optional[str] = None
        max_date: Optional[str] = None

        for txn in transactions:
            to_acct = txn.get("to_account", "UNKNOWN")
            amt = float(txn.get("amount", 0))
            counterparties[to_acct] = counterparties.get(to_acct, 0) + amt

            txn_date = txn.get("date") or txn.get("timestamp")
            if txn_date:
                if min_date is None or str(txn_date) < str(min_date):
                    min_date = str(txn_date)
                if max_date is None or str(txn_date) > str(max_date):
                    max_date = str(txn_date)

        # If no explicit transactions provided, use edge data
        if not transactions:
            for edge in alert_data.get("edges", []):
                to_acct = edge.get("to_account", "UNKNOWN")
                amt = float(edge.get("total_amount", 0))
                counterparties[to_acct] = counterparties.get(to_acct, 0) + amt
                txn_count = max(txn_count, edge.get("txn_count", 0))

        top_counterparties = sorted(
            counterparties.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:5]

        return {
            "total_amount": total_amount,
            "txn_count": txn_count,
            "date_range": {"from": min_date, "to": max_date},
            "top_counterparties": [
                {"account": cp[0], "amount": cp[1]} for cp in top_counterparties
            ],
        }

    @staticmethod
    def _build_graph_context(alert_data: Dict) -> Dict:
        """Extract graph neighborhood info — shared devices, IPs, cluster."""
        shared_devices = alert_data.get("shared_devices", [])
        shared_ips = alert_data.get("shared_ips", [])
        nodes = alert_data.get("nodes", [])
        edges = alert_data.get("edges", [])

        roles: Dict[str, int] = {}
        for node in nodes:
            role = node.get("role", "UNKNOWN")
            roles[role] = roles.get(role, 0) + 1

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "shared_devices": shared_devices,
            "shared_device_count": len(shared_devices),
            "shared_ips": shared_ips,
            "shared_ip_count": len(shared_ips),
            "cluster_id": alert_data.get("cluster_id"),
            "role_distribution": roles,
        }

    @staticmethod
    def _build_behavioral_profile(alert_data: Dict) -> Dict:
        """Extract behavioral baseline deviations from node data."""
        nodes = alert_data.get("nodes", [])
        deviations: List[Dict] = []

        for node in nodes:
            account_age = node.get("account_age_days")
            smurf_score = node.get("smurf_score", 0)
            kyc_status = node.get("kyc_status", "UNKNOWN")
            betweenness = node.get("betweenness_centrality", 0)

            flags: List[str] = []
            if account_age is not None and account_age < THRESHOLD_YOUNG_ACCOUNT_DAYS:
                flags.append(f"new_account ({account_age}d)")
            if smurf_score > THRESHOLD_HIGH_SMURF_SCORE:
                flags.append(f"high_smurf_score ({smurf_score:.2f})")
            if kyc_status == "PENDING":
                flags.append("kyc_pending")
            if betweenness > THRESHOLD_HIGH_BETWEENNESS:
                flags.append(f"high_centrality ({betweenness:.2f})")

            if flags:
                deviations.append(
                    {
                        "account_id": node.get("account_id"),
                        "flags": flags,
                        "smurf_score": smurf_score,
                        "account_age_days": account_age,
                    }
                )

        return {
            "deviation_count": len(deviations),
            "deviations": deviations,
            "gnn_score": alert_data.get("gnn_score"),
        }

    @staticmethod
    def _extract_screening_results(alert_data: Dict) -> Dict:
        """Parse screening / watchlist hits from reason codes."""
        reason_codes = alert_data.get("reason_codes", [])
        screening_hits: List[str] = []
        rule_triggers: List[str] = []

        for rc in reason_codes:
            lower = rc.lower()
            if "screen" in lower or "watchlist" in lower or "sanction" in lower:
                screening_hits.append(rc)
            else:
                rule_triggers.append(rc)

        return {
            "screening_hits": screening_hits,
            "rule_triggers": rule_triggers,
            "total_reason_codes": len(reason_codes),
        }

    @staticmethod
    def _extract_typology(alert_data: Dict) -> Optional[Dict]:
        """Extract typology classification if available."""
        edges = alert_data.get("edges", [])
        patterns = set()
        for edge in edges:
            pattern = edge.get("pattern")
            if pattern:
                patterns.add(pattern)

        if not patterns:
            return None

        return {
            "patterns": sorted(patterns),
            "primary_pattern": sorted(patterns)[0],
        }

    @staticmethod
    def _build_timeline(alert_data: Dict, transactions: List[Dict]) -> List[Dict]:
        """Build a chronological timeline of key events."""
        events: List[Dict] = []

        # Add node creation events
        for node in alert_data.get("nodes", []):
            age = node.get("account_age_days")
            if age is not None:
                events.append(
                    {
                        "event_type": "account_created",
                        "account_id": node.get("account_id"),
                        "days_ago": age,
                        "detail": f"Account opened {age} days ago",
                    }
                )

        # Add transaction events
        for txn in transactions:
            txn_date = txn.get("date") or txn.get("timestamp")
            events.append(
                {
                    "event_type": "transaction",
                    "date": str(txn_date) if txn_date else "unknown",
                    "from": txn.get("from_account"),
                    "to": txn.get("to_account"),
                    "amount": float(txn.get("amount", 0)),
                }
            )

        # Add alert generation event
        events.append(
            {
                "event_type": "alert_generated",
                "alert_id": alert_data.get("alert_id"),
                "severity": alert_data.get("severity"),
                "risk_score": alert_data.get("risk_score"),
            }
        )

        return events

    @staticmethod
    def _classify_evidence(
        alert_data: Dict,
        transaction_summary: Dict,
        graph_context: Dict,
        behavioral_profile: Dict,
        screening_results: Dict,
    ) -> List[EvidenceItem]:
        """Classify all evidence items with severity levels."""
        items: List[EvidenceItem] = []

        # Transaction evidence
        total = transaction_summary.get("total_amount", 0)
        if total > 0:
            severity = (
                "HIGH" if total > 500_000 else ("MEDIUM" if total > 100_000 else "LOW")
            )
            items.append(
                EvidenceItem(
                    evidence_type="transaction",
                    description=f"Total transactions: INR {total:,.0f} across {transaction_summary.get('txn_count', 0)} transactions",
                    data=transaction_summary,
                    severity=severity,
                )
            )

        # Graph / device evidence
        if graph_context.get("shared_device_count", 0) > 0:
            items.append(
                EvidenceItem(
                    evidence_type="device",
                    description=f"{graph_context['shared_device_count']} shared device(s) detected across accounts",
                    data={"shared_devices": graph_context["shared_devices"]},
                    severity="HIGH",
                )
            )

        if graph_context.get("shared_ip_count", 0) > 0:
            items.append(
                EvidenceItem(
                    evidence_type="graph",
                    description=f"{graph_context['shared_ip_count']} shared IP(s) detected",
                    data={"shared_ips": graph_context["shared_ips"]},
                    severity="MEDIUM",
                )
            )

        # Behavioral evidence
        for dev in behavioral_profile.get("deviations", []):
            smurf = dev.get("smurf_score", 0)
            severity = "HIGH" if smurf > THRESHOLD_HIGH_SEVERITY_SMURF else "MEDIUM"
            items.append(
                EvidenceItem(
                    evidence_type="behavioral",
                    description=f"Account {dev.get('account_id')}: {', '.join(dev.get('flags', []))}",
                    data=dev,
                    severity=severity,
                )
            )

        # Screening evidence
        for hit in screening_results.get("screening_hits", []):
            items.append(
                EvidenceItem(
                    evidence_type="screening",
                    description=hit,
                    data={"hit": hit},
                    severity="HIGH",
                )
            )

        return items

    @staticmethod
    def _assess_case_strength(evidence_items: List[EvidenceItem]) -> str:
        """Assess case strength based on evidence diversity and severity.

        STRONG: 3+ HIGH severity items
        MODERATE: 1-2 HIGH severity items
        WEAK: only MEDIUM/LOW items
        """
        high_count = sum(1 for e in evidence_items if e.severity == "HIGH")
        if high_count >= 3:
            return "STRONG"
        if high_count >= 1:
            return "MODERATE"
        return "WEAK"
