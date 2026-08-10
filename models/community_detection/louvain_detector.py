"""
MuleCatch Community Detection
==============================
Uses the Louvain algorithm on the transaction graph to identify
tightly connected communities of accounts — mule clusters.

Each community is scored for suspiciousness using:
  - Internal edge density
  - Shared device/IP fingerprints
  - Temporal co-activity
  - Account age distribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import networkx as nx
from community import best_partition  # python-louvain


@dataclass
class Community:
    community_id: int
    accounts: Set[str]
    internal_edges: int
    shared_devices: List[str]
    shared_ips: List[str]
    density: float
    suspicion_score: float = 0.0
    reason_codes: List[str] = field(default_factory=list)
    is_mule_cluster: bool = False
    size: int = 0


# -- Community suspicion scoring constants ------------------------------------
# Minimum suspicion score required to flag a community as a mule cluster
SUSPICION_THRESHOLD = 0.50
# Minimum number of accounts for a community to be considered
MIN_CLUSTER_SIZE = 3
# Minimum edge density for a community to trigger reason code CC01
MIN_CLUSTER_DENSITY = 0.15

# -- Scoring component caps and multipliers -----------------------------------
# Maximum contribution from internal edge density (0-0.25)
DENSITY_SCORE_CAP = 0.25
# Density is multiplied by this before capping
DENSITY_MULTIPLIER = 2

# Maximum contribution from shared device fingerprints (0-0.25)
SHARED_DEVICE_SCORE_CAP = 0.25
# Score added per shared device fingerprint
SHARED_DEVICE_SCORE_PER = 0.08

# Maximum contribution from shared IP addresses (0-0.20)
SHARED_IP_SCORE_CAP = 0.20
# Score added per shared IP address
SHARED_IP_SCORE_PER = 0.07

# Maximum contribution from young/very-young accounts (0-0.20)
YOUNG_ACCOUNT_SCORE_CAP = 0.20
# Score weight for accounts younger than 30 days
YOUNG_ACCOUNT_WEIGHT = 0.10
# Score weight for accounts younger than 7 days
VERY_YOUNG_ACCOUNT_WEIGHT = 0.10

# Account age thresholds (days)
VERY_YOUNG_ACCOUNT_DAYS = 7
YOUNG_ACCOUNT_DAYS = 30

# Maximum contribution from pending KYC ratio (0-0.10)
PENDING_KYC_SCORE_CAP = 0.10
# KYC pending ratio multiplier
PENDING_KYC_WEIGHT = 0.10

# Bonus for clusters spanning more than this many banks (layering signal)
MIXED_BANK_THRESHOLD = 2
MIXED_BANK_BONUS = 0.10

# Bonus for large clusters (>= this many accounts)
LARGE_CLUSTER_SIZE = 10
LARGE_CLUSTER_BONUS = 0.05

# Shared device edge weight bonus in graph construction
SHARED_DEVICE_EDGE_WEIGHT = 2

# Minimum cluster size for reason code CC04
LARGE_GROUP_REASON_CODE_SIZE = 6

# Stable graph partitioning for reproducible alerts and audit evidence.
LOUVAIN_RANDOM_STATE = 42

# -- CBS behavioral feature scoring constants ---------------------------------
# CBS pass-through ratio scoring
CBS_PASS_THROUGH_MIN = 0.5
CBS_PASS_THROUGH_MULTIPLIER = 0.15
CBS_PASS_THROUGH_CAP = 0.12

# CBS debit/credit ratio near 1.0 range
CBS_DC_RATIO_LOW = 0.7
CBS_DC_RATIO_HIGH = 1.3
CBS_DC_RATIO_WEIGHT = 0.10
CBS_DC_RATIO_CAP = 0.10

# CBS negative balance scoring
CBS_NEGATIVE_BALANCE_WEIGHT = 0.10
CBS_NEGATIVE_BALANCE_CAP = 0.08

# CBS balance volatility thresholds
CBS_HIGH_VOLATILITY = 5000
CBS_HIGH_VOLATILITY_BONUS = 0.05
CBS_MEDIUM_VOLATILITY = 1000
CBS_MEDIUM_VOLATILITY_BONUS = 0.03


class LouvainClusterDetector:
    """
    Builds a transaction graph and applies Louvain community detection.
    Communities with high internal density + shared fingerprints are flagged.
    """

    SUSPICION_THRESHOLD = SUSPICION_THRESHOLD
    MIN_CLUSTER_SIZE = MIN_CLUSTER_SIZE
    MIN_CLUSTER_DENSITY = MIN_CLUSTER_DENSITY

    def detect_clusters(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> List[Community]:
        G = self._build_graph(transactions, accounts)
        if len(G.nodes) < self.MIN_CLUSTER_SIZE:
            return []

        # Store graph for centrality queries
        self._graph = G

        partition = best_partition(
            G,
            weight="weight",
            random_state=LOUVAIN_RANDOM_STATE,
        )
        communities = self._build_communities(G, partition, transactions, accounts)
        return [c for c in communities if c.size >= self.MIN_CLUSTER_SIZE]

    def compute_centrality(self) -> Dict[str, Dict[str, float]]:
        """Compute betweenness centrality and PageRank on the transaction graph.

        Returns dict mapping account_id -> {"betweenness": float, "pagerank": float}.
        Must be called after detect_clusters().
        """
        G = getattr(self, "_graph", None)
        if G is None or len(G.nodes) == 0:
            return {}

        betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
        pagerank = nx.pagerank(G, weight="weight", max_iter=100)

        result: Dict[str, Dict[str, float]] = {}
        for node in G.nodes:
            result[node] = {
                "betweenness": round(betweenness.get(node, 0.0), 6),
                "pagerank": round(pagerank.get(node, 0.0), 6),
            }
        return result

    def _build_graph(
        self,
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> nx.Graph:
        G = nx.Graph()

        # Add account nodes
        for acc in accounts:
            G.add_node(
                acc["account_id"],
                role=acc.get("role", "UNKNOWN"),
                bank=acc.get("bank", ""),
                age=acc.get("account_age_days", 0),
                cluster_id=acc.get("cluster_id", ""),
            )

        # Add weighted edges (more transactions = stronger edge)
        edge_weights: Dict[Tuple[str, str], float] = {}
        for t in transactions:
            src = t["from_account"]
            dst = t["to_account"]
            if src not in G.nodes or dst not in G.nodes:
                continue
            key = (min(src, dst), max(src, dst))
            edge_weights[key] = edge_weights.get(key, 0) + 1

        for (src, dst), w in edge_weights.items():
            G.add_edge(src, dst, weight=w)

        # Add device-sharing edges (strong signal)
        device_map: Dict[str, List[str]] = {}
        for t in transactions:
            dev = t.get("device_id", "")
            acc = t["from_account"]
            if dev:
                device_map.setdefault(dev, []).append(acc)

        for dev, accs in device_map.items():
            unique = list(set(accs))
            for i in range(len(unique)):
                for j in range(i + 1, len(unique)):
                    a, b = unique[i], unique[j]
                    if a in G.nodes and b in G.nodes:
                        if G.has_edge(a, b):
                            G[a][b]["weight"] += SHARED_DEVICE_EDGE_WEIGHT
                        else:
                            G.add_edge(a, b, weight=SHARED_DEVICE_EDGE_WEIGHT)

        return G

    def _build_communities(
        self,
        G: nx.Graph,
        partition: Dict[str, int],
        transactions: List[Dict],
        accounts: List[Dict],
    ) -> List[Community]:
        communities: Dict[int, Set[str]] = {}
        for node, comm_id in partition.items():
            communities.setdefault(comm_id, set()).add(node)

        # Build device / IP lookup
        device_to_accounts: Dict[str, List[str]] = {}
        ip_to_accounts: Dict[str, List[str]] = {}
        for t in transactions:
            dev = t.get("device_id", "")
            ip = t.get("ip_address", "")
            src = t["from_account"]
            if dev:
                device_to_accounts.setdefault(dev, []).append(src)
            if ip:
                ip_to_accounts.setdefault(ip, []).append(src)

        results = []
        for comm_id, members in communities.items():
            if len(members) < self.MIN_CLUSTER_SIZE:
                continue

            subgraph = G.subgraph(members)
            n = len(members)
            max_edges = n * (n - 1) / 2
            internal_edges = subgraph.number_of_edges()
            density = internal_edges / max_edges if max_edges > 0 else 0.0

            # Shared devices within this community
            shared_devs = [dev for dev, accs in device_to_accounts.items() if len(set(accs) & members) >= 2]
            shared_ips = [ip for ip, accs in ip_to_accounts.items() if len(set(accs) & members) >= 2]

            community = Community(
                community_id=comm_id,
                accounts=members,
                internal_edges=internal_edges,
                shared_devices=shared_devs,
                shared_ips=shared_ips,
                density=density,
                size=n,
            )

            community.suspicion_score = self._score_community(community, accounts, members)
            community.reason_codes = self._reason_codes(community)
            community.is_mule_cluster = community.suspicion_score >= self.SUSPICION_THRESHOLD

            results.append(community)

        return sorted(results, key=lambda c: -c.suspicion_score)

    def _score_community(
        self,
        c: Community,
        accounts: List[Dict],
        members: Set[str],
    ) -> float:
        score = 0.0
        acc_map = {a["account_id"]: a for a in accounts if a["account_id"] in members}

        # Density contribution (0-DENSITY_SCORE_CAP)
        score += min(c.density * DENSITY_MULTIPLIER, DENSITY_SCORE_CAP)

        # Shared device fingerprints (0-SHARED_DEVICE_SCORE_CAP)
        score += min(len(c.shared_devices) * SHARED_DEVICE_SCORE_PER, SHARED_DEVICE_SCORE_CAP)

        # Shared IP addresses (0-SHARED_IP_SCORE_CAP)
        score += min(len(c.shared_ips) * SHARED_IP_SCORE_PER, SHARED_IP_SCORE_CAP)

        # Young accounts - very young (<7d) score higher (0-YOUNG_ACCOUNT_SCORE_CAP)
        ages = [a.get("account_age_days", 999) for a in acc_map.values()]
        very_young = sum(1 for age in ages if age < VERY_YOUNG_ACCOUNT_DAYS)
        young = sum(1 for age in ages if age < YOUNG_ACCOUNT_DAYS)
        young_ratio = young / max(len(ages), 1)
        very_young_ratio = very_young / max(len(ages), 1)
        score += min(
            young_ratio * YOUNG_ACCOUNT_WEIGHT + very_young_ratio * VERY_YOUNG_ACCOUNT_WEIGHT,
            YOUNG_ACCOUNT_SCORE_CAP,
        )

        # Pending KYC ratio (0-PENDING_KYC_SCORE_CAP)
        pending = sum(1 for a in acc_map.values() if a.get("kyc_status") == "PENDING")
        score += min(pending / max(len(acc_map), 1) * PENDING_KYC_WEIGHT, PENDING_KYC_SCORE_CAP)

        # Mixed banks (multiple banks = intentional layering)
        banks = set(a.get("bank", "") for a in acc_map.values())
        if len(banks) > MIXED_BANK_THRESHOLD:
            score += MIXED_BANK_BONUS

        # Cluster size bonus (larger = more suspicious)
        if c.size >= LARGE_CLUSTER_SIZE:
            score += LARGE_CLUSTER_BONUS

        # CBS behavioral features (compensate when device/IP data is absent)
        # These features are set by MuleCSVAdapter for CBS transaction data.
        has_cbs_features = any("pass_through_ratio" in a for a in acc_map.values())
        if has_cbs_features:
            score += self._score_cbs_features(acc_map)

        return min(score, 1.0)

    @staticmethod
    def _score_cbs_features(acc_map: Dict[str, Dict]) -> float:
        """Score CBS-specific behavioral features (0-0.35).

        Compensates for missing device/IP data in CBS exports by using
        transaction-derived features: pass-through ratio, debit/credit
        ratio, balance volatility, and negative balances.
        """
        if not acc_map:
            return 0.0

        boost = 0.0
        n = len(acc_map)

        # Pass-through ratio: accounts where money enters and leaves same day
        # High ratio across cluster = coordinated pass-through (0-CBS_PASS_THROUGH_CAP)
        pt_ratios = [a.get("pass_through_ratio", 0.0) for a in acc_map.values()]
        avg_pt = sum(pt_ratios) / n
        if avg_pt >= CBS_PASS_THROUGH_MIN:
            boost += min(avg_pt * CBS_PASS_THROUGH_MULTIPLIER, CBS_PASS_THROUGH_CAP)

        # Debit/credit ratio near 1.0: in ~= out = pass-through behavior (0-CBS_DC_RATIO_CAP)
        dc_ratios = [a.get("debit_credit_ratio", 0.0) for a in acc_map.values()]
        near_one = sum(1 for r in dc_ratios if CBS_DC_RATIO_LOW <= r <= CBS_DC_RATIO_HIGH)
        near_one_ratio = near_one / n
        boost += min(near_one_ratio * CBS_DC_RATIO_WEIGHT, CBS_DC_RATIO_CAP)

        # Negative balances: overdraft abuse is a mule indicator (0-CBS_NEGATIVE_BALANCE_CAP)
        neg_counts = [a.get("negative_balance_count", 0) for a in acc_map.values()]
        accts_with_neg = sum(1 for c in neg_counts if c > 0)
        neg_ratio = accts_with_neg / n
        boost += min(neg_ratio * CBS_NEGATIVE_BALANCE_WEIGHT, CBS_NEGATIVE_BALANCE_CAP)

        # Balance volatility: high avg volatility = funds rapidly moving (0-CBS_HIGH_VOLATILITY_BONUS)
        vols = [a.get("balance_volatility", 0.0) for a in acc_map.values()]
        avg_vol = sum(vols) / n if vols else 0
        if avg_vol > CBS_HIGH_VOLATILITY:
            boost += CBS_HIGH_VOLATILITY_BONUS
        elif avg_vol > CBS_MEDIUM_VOLATILITY:
            boost += CBS_MEDIUM_VOLATILITY_BONUS

        return boost

    def _reason_codes(self, c: Community) -> List[str]:
        codes = []
        if c.density >= self.MIN_CLUSTER_DENSITY:
            codes.append(f"CC01: Dense transaction cluster (density={c.density:.2f})")
        if c.shared_devices:
            codes.append(f"CC02: {len(c.shared_devices)} shared device fingerprint(s) across accounts")
        if c.shared_ips:
            codes.append(f"CC03: {len(c.shared_ips)} shared IP address(es) across accounts")
        if c.size >= LARGE_GROUP_REASON_CODE_SIZE:
            codes.append(f"CC04: Large interconnected group ({c.size} accounts)")
        return codes


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from data.synthetic.generator import build_full_dataset

    dataset = build_full_dataset(num_clusters=3, num_legit_accounts=20)
    detector = LouvainClusterDetector()
    communities = detector.detect_clusters(dataset["transactions"], dataset["accounts"])

    flagged = [c for c in communities if c.is_mule_cluster]
    print(f"Found {len(communities)} communities — {len(flagged)} flagged as mule clusters")
    for c in flagged:
        print(
            f"  Community {c.community_id}: {c.size} accounts, "
            f"score={c.suspicion_score:.3f}, "
            f"shared_devices={len(c.shared_devices)}"
        )
        for rc in c.reason_codes:
            print(f"    {rc}")
