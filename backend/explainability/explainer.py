"""
MuleCatch Explainability Engine
================================
Generates human-readable, auditor-friendly explanations for every alert.

Three explanation layers:
  1. Score Decomposition — SHAP-like feature importance showing how each
     detection layer contributed to the final risk score
  2. Fraud Chain Narrative — BFS traversal of the transaction graph
     producing a step-by-step money flow story
  3. Cycle Detection — identifies round-trip fraud rings where money
     circles back to the originator

References:
  - SHAP (Lundberg & Lee, 2017) — feature importance via Shapley values
  - BFS explainer pattern from vrks5331/Graph-Based-Fraud-Detection-Network
  - Cycle detection from dibyanshu-8/Graph-Anomaly-Detection
"""

from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Set, Optional, Tuple
import networkx as nx


# ── Data models ───────────────────────────────────────────────────────────

@dataclass
class FeatureContribution:
    """A single feature's contribution to the risk score."""
    feature: str
    value: float
    weight: float
    contribution: float  # value * weight (normalised)
    description: str
    severity: str  # HIGH | MEDIUM | LOW


@dataclass
class FraudChainStep:
    """One step in a fraud money-flow chain."""
    step: int
    from_account: str
    to_account: str
    amount: float
    txn_count: int
    pattern: str
    description: str


@dataclass
class CycleInfo:
    """A detected money cycle (round-trip ring)."""
    accounts: List[str]
    total_amount: float
    cycle_length: int
    description: str


@dataclass
class AlertExplanation:
    """Complete explanation package for an alert."""
    alert_id: str
    risk_score: float
    severity: str

    # Layer 1: Score decomposition
    score_breakdown: List[FeatureContribution]
    score_narrative: str

    # Layer 2: Fraud chain
    fraud_chain: List[FraudChainStep]
    chain_narrative: str

    # Layer 3: Cycles
    cycles: List[CycleInfo]
    cycle_narrative: str

    # Overall
    summary: str
    recommendation: str
    confidence_factors: List[str]

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "score_breakdown": [asdict(s) for s in self.score_breakdown],
            "score_narrative": self.score_narrative,
            "fraud_chain": [asdict(s) for s in self.fraud_chain],
            "chain_narrative": self.chain_narrative,
            "cycles": [asdict(c) for c in self.cycles],
            "cycle_narrative": self.cycle_narrative,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "confidence_factors": self.confidence_factors,
        }


# ── Score Decomposition (SHAP-like) ──────────────────────────────────────

def decompose_score(alert: Dict, smurf_scores: Dict = None) -> List[FeatureContribution]:
    """
    Decomposes the alert risk score into feature-level contributions,
    similar to SHAP waterfall charts. Shows investigators exactly WHY
    a score is what it is.
    """
    contributions = []
    nodes = alert.get("nodes", [])
    edges = alert.get("edges", [])
    reason_codes = alert.get("reason_codes", [])

    # Community density / topology
    account_count = alert.get("account_count", 0)
    density_signal = min(account_count / 15.0, 1.0)
    contributions.append(FeatureContribution(
        feature="cluster_size",
        value=account_count,
        weight=0.15,
        contribution=round(density_signal * 0.15, 4),
        description=f"{account_count} accounts form a tightly connected cluster",
        severity="HIGH" if account_count >= 8 else "MEDIUM",
    ))

    # Shared device fingerprints
    shared_devs = alert.get("shared_devices", [])
    dev_signal = min(len(shared_devs) * 0.3, 1.0)
    if shared_devs:
        contributions.append(FeatureContribution(
            feature="shared_devices",
            value=len(shared_devs),
            weight=0.20,
            contribution=round(dev_signal * 0.20, 4),
            description=f"{len(shared_devs)} device(s) shared across multiple accounts — strong collusion signal",
            severity="HIGH",
        ))

    # Shared IP addresses
    shared_ips = alert.get("shared_ips", [])
    ip_signal = min(len(shared_ips) * 0.25, 1.0)
    if shared_ips:
        contributions.append(FeatureContribution(
            feature="shared_ips",
            value=len(shared_ips),
            weight=0.15,
            contribution=round(ip_signal * 0.15, 4),
            description=f"{len(shared_ips)} IP address(es) shared — accounts operated from same location",
            severity="HIGH" if len(shared_ips) >= 2 else "MEDIUM",
        ))

    # Smurf scoring sub-components (if available)
    if smurf_scores and nodes:
        max_velocity = 0.0
        max_ceiling = 0.0
        max_fanout = 0.0
        max_rhythm = 0.0
        max_consolidation = 0.0

        for n in nodes:
            ss = smurf_scores.get(n.get("account_id") if isinstance(n, dict) else n.account_id)
            if ss:
                max_velocity = max(max_velocity, ss.velocity_score if hasattr(ss, 'velocity_score') else 0)
                max_ceiling = max(max_ceiling, ss.amount_ceiling_score if hasattr(ss, 'amount_ceiling_score') else 0)
                max_fanout = max(max_fanout, ss.fan_out_score if hasattr(ss, 'fan_out_score') else 0)
                max_rhythm = max(max_rhythm, ss.rhythm_score if hasattr(ss, 'rhythm_score') else 0)
                max_consolidation = max(max_consolidation, ss.consolidation_score if hasattr(ss, 'consolidation_score') else 0)

        if max_velocity > 0.3:
            contributions.append(FeatureContribution(
                feature="transaction_velocity",
                value=round(max_velocity, 3),
                weight=0.25,
                contribution=round(max_velocity * 0.25, 4),
                description=f"Burst of transactions detected — {round(max_velocity * 12):.0f}+ txns/hour peak",
                severity="HIGH" if max_velocity > 0.6 else "MEDIUM",
            ))

        if max_ceiling > 0.3:
            contributions.append(FeatureContribution(
                feature="amount_structuring",
                value=round(max_ceiling, 3),
                weight=0.25,
                contribution=round(max_ceiling * 0.25, 4),
                description="Amounts deliberately kept just below the ₹50,000 reporting threshold",
                severity="HIGH" if max_ceiling > 0.6 else "MEDIUM",
            ))

        if max_fanout > 0.3:
            contributions.append(FeatureContribution(
                feature="fan_out_pattern",
                value=round(max_fanout, 3),
                weight=0.20,
                contribution=round(max_fanout * 0.20, 4),
                description=f"Funds dispersed to {round(max_fanout * 8):.0f}+ unique recipients — layering behavior",
                severity="HIGH" if max_fanout > 0.5 else "MEDIUM",
            ))

        if max_rhythm > 0.3:
            contributions.append(FeatureContribution(
                feature="bot_like_rhythm",
                value=round(max_rhythm, 3),
                weight=0.15,
                contribution=round(max_rhythm * 0.15, 4),
                description="Suspiciously regular transaction intervals — likely automated",
                severity="MEDIUM",
            ))

        if max_consolidation > 0.3:
            contributions.append(FeatureContribution(
                feature="rapid_consolidation",
                value=round(max_consolidation, 3),
                weight=0.15,
                contribution=round(max_consolidation * 0.15, 4),
                description="Funds received and re-sent within hours — classic mule pass-through",
                severity="HIGH" if max_consolidation > 0.5 else "MEDIUM",
            ))
    else:
        # Fallback: decompose from reason codes
        smurf_codes = [rc for rc in reason_codes if rc.startswith("RC")]
        if smurf_codes:
            per_code = 0.10
            for rc in smurf_codes:
                contributions.append(FeatureContribution(
                    feature="smurf_signal",
                    value=1.0,
                    weight=per_code,
                    contribution=per_code,
                    description=rc.split(": ", 1)[1] if ": " in rc else rc,
                    severity="HIGH",
                ))

    # Rule engine hits
    rule_codes = [rc for rc in reason_codes if rc.startswith("R0")]
    if rule_codes:
        rule_contribution = min(len(rule_codes) * 0.05, 0.15)
        contributions.append(FeatureContribution(
            feature="rule_engine_hits",
            value=len(rule_codes),
            weight=0.10,
            contribution=round(rule_contribution, 4),
            description=f"{len(rule_codes)} deterministic rule(s) triggered: {', '.join(rc.split(':')[0] for rc in rule_codes)}",
            severity="HIGH" if len(rule_codes) >= 3 else "MEDIUM",
        ))

    # GNN score (if present)
    gnn_score = alert.get("gnn_score")
    if gnn_score is not None and gnn_score > 0:
        contributions.append(FeatureContribution(
            feature="gnn_graph_learning",
            value=round(gnn_score, 3),
            weight=0.20,
            contribution=round(gnn_score * 0.20, 4),
            description=f"Graph neural network classified cluster as {round(gnn_score * 100)}% likely mule network",
            severity="HIGH" if gnn_score > 0.7 else "MEDIUM",
        ))

    # Sort by contribution descending
    contributions.sort(key=lambda c: -c.contribution)
    return contributions


def build_score_narrative(contributions: List[FeatureContribution], risk_score: float) -> str:
    """Generates a plain-English paragraph explaining the risk score."""
    if not contributions:
        return "Insufficient data to explain this score."

    top_3 = contributions[:3]
    parts = []
    for c in top_3:
        parts.append(c.description)

    narrative = (
        f"This alert has a risk score of {round(risk_score * 100)}%. "
        f"The primary drivers are: {parts[0]}."
    )
    if len(parts) > 1:
        narrative += f" Additionally, {parts[1].lower()}."
    if len(parts) > 2:
        narrative += f" {parts[2]}."

    return narrative


# ── Fraud Chain Explainer (BFS) ──────────────────────────────────────────

def trace_fraud_chain(alert: Dict) -> List[FraudChainStep]:
    """
    BFS traversal of the alert's transaction subgraph to produce
    a human-readable money-flow chain. Identifies the SOURCE node
    and traces how money flows through MULE layers to AGGREGATORS.

    Inspired by: vrks5331/Graph-Based-Fraud-Detection-Network
    """
    nodes = alert.get("nodes", [])
    edges = alert.get("edges", [])

    if not nodes or not edges:
        return []

    # Build role lookup
    role_map = {}
    for n in nodes:
        acc_id = n.get("account_id") if isinstance(n, dict) else n.account_id
        role = n.get("role") if isinstance(n, dict) else n.role
        role_map[acc_id] = role

    # Build adjacency from edges
    adj: Dict[str, List[Dict]] = defaultdict(list)
    for e in edges:
        src = e.get("from_account") if isinstance(e, dict) else e.from_account
        dst = e.get("to_account") if isinstance(e, dict) else e.to_account
        amount = float(e.get("total_amount") if isinstance(e, dict) else e.total_amount)
        txn_count = int(e.get("txn_count") if isinstance(e, dict) else e.txn_count)
        pattern = e.get("pattern", "NORMAL") if isinstance(e, dict) else e.pattern
        adj[src].append({
            "to": dst, "amount": amount, "txn_count": txn_count, "pattern": pattern
        })

    # Find SOURCE nodes (entry points)
    sources = [acc for acc, role in role_map.items() if role == "SOURCE"]
    if not sources:
        # Fallback: use nodes with highest outgoing volume
        out_volume = defaultdict(float)
        for e in edges:
            src = e.get("from_account") if isinstance(e, dict) else e.from_account
            amount = float(e.get("total_amount") if isinstance(e, dict) else e.total_amount)
            out_volume[src] += amount
        if out_volume:
            sources = [max(out_volume, key=out_volume.get)]

    if not sources:
        return []

    # BFS from source
    chain: List[FraudChainStep] = []
    visited: Set[str] = set()
    queue = deque()

    for src in sources:
        queue.append(src)
        visited.add(src)

    step_num = 0
    while queue and step_num < 20:
        current = queue.popleft()
        for edge in adj.get(current, []):
            dst = edge["to"]
            if dst in visited:
                continue
            visited.add(dst)
            step_num += 1

            dst_role = role_map.get(dst, "UNKNOWN")
            src_role = role_map.get(current, "UNKNOWN")

            description = _describe_flow_step(
                current, dst, src_role, dst_role,
                edge["amount"], edge["txn_count"], edge["pattern"]
            )

            chain.append(FraudChainStep(
                step=step_num,
                from_account=current,
                to_account=dst,
                amount=edge["amount"],
                txn_count=edge["txn_count"],
                pattern=edge["pattern"],
                description=description,
            ))

            queue.append(dst)

    return chain


def _describe_flow_step(
    src: str, dst: str,
    src_role: str, dst_role: str,
    amount: float, txn_count: int, pattern: str
) -> str:
    """Human-readable description of a money flow step."""
    amount_str = f"₹{amount:,.0f}"
    src_short = src[-8:]
    dst_short = dst[-8:]

    if src_role == "SOURCE":
        verb = "originates"
    elif dst_role == "AGGREGATOR":
        verb = "consolidates into"
    else:
        verb = "passes through to"

    base = f"{amount_str} ({txn_count} txn{'s' if txn_count > 1 else ''}) {verb} ...{dst_short}"

    if pattern == "RAPID_BURST":
        base += " via rapid burst"
    elif pattern == "STRUCTURING":
        base += " in structured amounts below threshold"
    elif pattern == "ROUND_TRIP":
        base += " in a circular pattern"
    elif pattern == "LAYERING":
        base += " through layering"

    if dst_role == "AGGREGATOR":
        base += " [AGGREGATION POINT]"
    elif dst_role == "MULE":
        base += " [MULE LAYER]"

    return base


def build_chain_narrative(chain: List[FraudChainStep], alert: Dict) -> str:
    """Produces a paragraph summarizing the money flow."""
    if not chain:
        return "No clear money flow chain could be traced in this cluster."

    total = sum(s.amount for s in chain)
    steps = len(chain)
    unique_accounts = set()
    for s in chain:
        unique_accounts.add(s.from_account)
        unique_accounts.add(s.to_account)

    narrative = (
        f"Money flow analysis traces ₹{total:,.0f} across {steps} "
        f"transfer step{'s' if steps > 1 else ''} involving "
        f"{len(unique_accounts)} accounts. "
    )

    sources = [s for s in chain if s.step == 1]
    if sources:
        narrative += (
            f"Funds originate from ...{sources[0].from_account[-8:]} "
            f"and flow through {steps - 1} intermediate hop{'s' if steps > 2 else ''}. "
        )

    patterns = set(s.pattern for s in chain if s.pattern != "NORMAL")
    if patterns:
        narrative += f"Detected patterns: {', '.join(p.replace('_', ' ').title() for p in patterns)}. "

    return narrative


# ── Cycle Detection ──────────────────────────────────────────────────────

def detect_cycles(alert: Dict) -> List[CycleInfo]:
    """
    Detects money cycles (round-trip fraud) in the alert subgraph.
    A cycle means money sent from A eventually returns to A,
    indicating circular layering / round-tripping.

    Uses NetworkX simple_cycles on a directed graph.
    Inspired by: dibyanshu-8/Graph-Anomaly-Detection
    """
    edges = alert.get("edges", [])
    if not edges:
        return []

    G = nx.DiGraph()
    edge_amounts: Dict[Tuple[str, str], float] = {}

    for e in edges:
        src = e.get("from_account") if isinstance(e, dict) else e.from_account
        dst = e.get("to_account") if isinstance(e, dict) else e.to_account
        amount = float(e.get("total_amount") if isinstance(e, dict) else e.total_amount)
        G.add_edge(src, dst, weight=amount)
        edge_amounts[(src, dst)] = amount

    cycles = []
    try:
        cycle_count = 0
        for cycle_nodes in nx.simple_cycles(G, length_bound=8):
            cycle_count += 1
            if cycle_count > 50:
                break  # cap iterations to avoid exponential blowup
            if len(cycle_nodes) < 3:
                continue
            # Compute total amount in cycle
            total_amount = 0.0
            for i in range(len(cycle_nodes)):
                src = cycle_nodes[i]
                dst = cycle_nodes[(i + 1) % len(cycle_nodes)]
                total_amount += edge_amounts.get((src, dst), 0)

            short_ids = [f"...{a[-6:]}" for a in cycle_nodes]
            description = (
                f"Round-trip detected: {' → '.join(short_ids)} → {short_ids[0]}. "
                f"₹{total_amount:,.0f} circulated through {len(cycle_nodes)} accounts. "
                f"This is a strong indicator of circular layering / money laundering."
            )

            cycles.append(CycleInfo(
                accounts=cycle_nodes,
                total_amount=round(total_amount, 2),
                cycle_length=len(cycle_nodes),
                description=description,
            ))
    except (nx.NetworkXError, TypeError):
        # TypeError fallback: length_bound not supported in older networkx
        try:
            cycle_count = 0
            for cycle_nodes in nx.simple_cycles(G):
                cycle_count += 1
                if cycle_count > 50:
                    break
                if len(cycle_nodes) < 3 or len(cycle_nodes) > 8:
                    continue
                total_amount = 0.0
                for i in range(len(cycle_nodes)):
                    src = cycle_nodes[i]
                    dst = cycle_nodes[(i + 1) % len(cycle_nodes)]
                    total_amount += edge_amounts.get((src, dst), 0)

                short_ids = [f"...{a[-6:]}" for a in cycle_nodes]
                description = (
                    f"Round-trip detected: {' → '.join(short_ids)} → {short_ids[0]}. "
                    f"₹{total_amount:,.0f} circulated through {len(cycle_nodes)} accounts. "
                    f"This is a strong indicator of circular layering / money laundering."
                )
                cycles.append(CycleInfo(
                    accounts=cycle_nodes,
                    total_amount=round(total_amount, 2),
                    cycle_length=len(cycle_nodes),
                    description=description,
                ))
        except nx.NetworkXError:
            pass

    # Sort by amount descending
    cycles.sort(key=lambda c: -c.total_amount)
    return cycles[:5]  # limit to top 5 cycles


def build_cycle_narrative(cycles: List[CycleInfo]) -> str:
    if not cycles:
        return "No circular money flows (round-tripping) detected in this cluster."

    total = sum(c.total_amount for c in cycles)
    narrative = (
        f"Detected {len(cycles)} circular money flow{'s' if len(cycles) > 1 else ''} "
        f"totaling ₹{total:,.0f}. "
    )
    if len(cycles) == 1:
        c = cycles[0]
        narrative += (
            f"A {c.cycle_length}-account ring circulates ₹{c.total_amount:,.0f}, "
            f"strongly indicating round-trip laundering."
        )
    else:
        narrative += (
            f"The largest ring involves {cycles[0].cycle_length} accounts "
            f"circulating ₹{cycles[0].total_amount:,.0f}."
        )
    return narrative


# ── Confidence Factors ───────────────────────────────────────────────────

def build_confidence_factors(alert: Dict, contributions: List[FeatureContribution]) -> List[str]:
    """Lists factors that increase or decrease confidence in the alert."""
    factors = []

    high_count = sum(1 for c in contributions if c.severity == "HIGH")
    if high_count >= 3:
        factors.append(f"Strong confidence: {high_count} high-severity signals converge")
    elif high_count >= 1:
        factors.append(f"Moderate confidence: {high_count} high-severity signal(s) detected")

    if alert.get("shared_devices"):
        factors.append("Device fingerprint sharing provides strong physical evidence")

    if alert.get("gnn_score") and alert["gnn_score"] > 0.7:
        factors.append("GNN graph learning independently confirms high mule probability")

    nodes = alert.get("nodes", [])
    young_accounts = sum(
        1 for n in nodes
        if (n.get("account_age_days") if isinstance(n, dict) else getattr(n, 'account_age_days', 999)) < 30
    )
    if young_accounts >= 2:
        factors.append(f"{young_accounts} accounts are less than 30 days old — elevated risk")

    pending_kyc = sum(
        1 for n in nodes
        if (n.get("kyc_status") if isinstance(n, dict) else getattr(n, 'kyc_status', '')) == "PENDING"
    )
    if pending_kyc:
        factors.append(f"{pending_kyc} account(s) have incomplete KYC verification")

    reason_codes = alert.get("reason_codes", [])
    if len(reason_codes) >= 5:
        factors.append(f"{len(reason_codes)} distinct reason codes — multi-signal convergence")

    return factors


# ── Recommendation Engine ────────────────────────────────────────────────

def build_recommendation(alert: Dict, cycles: List[CycleInfo]) -> str:
    """Generates an actionable recommendation for the investigator."""
    severity = alert.get("severity", "MEDIUM")
    risk = alert.get("risk_score", 0)

    if severity == "CRITICAL":
        rec = "IMMEDIATE ACTION REQUIRED: "
        if cycles:
            rec += (
                "Round-trip money laundering detected. Freeze accounts in the "
                "circular ring, file STR with FIU-IND immediately, and escalate "
                "to the compliance officer."
            )
        else:
            rec += (
                "High-confidence mule network identified. File STR with FIU-IND, "
                "freeze SOURCE and AGGREGATOR accounts, and flag all MULE accounts "
                "for enhanced due diligence."
            )
    elif severity == "HIGH":
        rec = (
            "HIGH PRIORITY: Review the network topology and money flow chain. "
            "If the fraud chain narrative confirms layering behavior, proceed "
            "with STR filing. Consider placing transaction holds on flagged accounts."
        )
    else:
        rec = (
            "REVIEW RECOMMENDED: This cluster shows moderate suspicious activity. "
            "Examine the reason codes and transaction velocity patterns. "
            "Monitor for escalation before filing STR."
        )

    return rec


# ── Main Explainer ───────────────────────────────────────────────────────

def explain_alert(alert: Dict, smurf_scores: Dict = None) -> AlertExplanation:
    """
    Master function: produces a complete explanation for one alert.
    Called by the API layer after detection pipeline runs.
    """
    risk_score = alert.get("risk_score", 0)
    severity = alert.get("severity", "MEDIUM")

    # 1. Score decomposition
    contributions = decompose_score(alert, smurf_scores)
    score_narrative = build_score_narrative(contributions, risk_score)

    # 2. Fraud chain
    chain = trace_fraud_chain(alert)
    chain_narrative = build_chain_narrative(chain, alert)

    # 3. Cycle detection
    cycles = detect_cycles(alert)
    cycle_narrative = build_cycle_narrative(cycles)

    # 4. Confidence & recommendation
    confidence_factors = build_confidence_factors(alert, contributions)
    recommendation = build_recommendation(alert, cycles)

    # 5. Executive summary
    summary = (
        f"{severity} alert with {round(risk_score * 100)}% risk score. "
        f"{len(contributions)} risk factors identified across {alert.get('account_count', 0)} accounts. "
    )
    if chain:
        summary += f"Money flow traces {len(chain)} transfer hops. "
    if cycles:
        summary += f"{len(cycles)} round-trip ring(s) detected. "
    summary += recommendation.split(".")[0] + "."

    return AlertExplanation(
        alert_id=alert.get("alert_id", ""),
        risk_score=risk_score,
        severity=severity,
        score_breakdown=contributions,
        score_narrative=score_narrative,
        fraud_chain=chain,
        chain_narrative=chain_narrative,
        cycles=cycles,
        cycle_narrative=cycle_narrative,
        summary=summary,
        recommendation=recommendation,
        confidence_factors=confidence_factors,
    )
