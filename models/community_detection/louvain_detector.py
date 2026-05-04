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
from typing import List, Dict, Set, Optional, Tuple
import networkx as nx
from community import best_partition   # python-louvain


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


class LouvainClusterDetector:
    """
    Builds a transaction graph and applies Louvain community detection.
    Communities with high internal density + shared fingerprints are flagged.
    """

    SUSPICION_THRESHOLD = 0.50
    MIN_CLUSTER_SIZE    = 3
    MIN_CLUSTER_DENSITY = 0.15

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

        partition = best_partition(G, weight="weight")
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
        acc_meta = {a["account_id"]: a for a in accounts}
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
                            G[a][b]["weight"] += 2  # shared device = extra weight
                        else:
                            G.add_edge(a, b, weight=2)

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
            ip  = t.get("ip_address", "")
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
            shared_devs = [
                dev for dev, accs in device_to_accounts.items()
                if len(set(accs) & members) >= 2
            ]
            shared_ips = [
                ip for ip, accs in ip_to_accounts.items()
                if len(set(accs) & members) >= 2
            ]

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

        # Density contribution (0-0.25)
        score += min(c.density * 2, 0.25)

        # Shared device fingerprints (0-0.25)
        score += min(len(c.shared_devices) * 0.08, 0.25)

        # Shared IP addresses (0-0.20)
        score += min(len(c.shared_ips) * 0.07, 0.20)

        # Young accounts - very young (<7d) score higher (0-0.20)
        ages = [a.get("account_age_days", 999) for a in acc_map.values()]
        very_young = sum(1 for age in ages if age < 7)
        young = sum(1 for age in ages if age < 30)
        young_ratio = young / max(len(ages), 1)
        very_young_ratio = very_young / max(len(ages), 1)
        score += min(young_ratio * 0.10 + very_young_ratio * 0.10, 0.20)

        # Pending KYC ratio (0-0.10)
        pending = sum(1 for a in acc_map.values() if a.get("kyc_status") == "PENDING")
        score += min(pending / max(len(acc_map), 1) * 0.10, 0.10)

        # Mixed banks (multiple banks = intentional layering)
        banks = set(a.get("bank", "") for a in acc_map.values())
        if len(banks) > 2:
            score += 0.10

        # Cluster size bonus (larger = more suspicious)
        if c.size >= 10:
            score += 0.05

        return min(score, 1.0)

    def _reason_codes(self, c: Community) -> List[str]:
        codes = []
        if c.density >= self.MIN_CLUSTER_DENSITY:
            codes.append(f"CC01: Dense transaction cluster (density={c.density:.2f})")
        if c.shared_devices:
            codes.append(f"CC02: {len(c.shared_devices)} shared device fingerprint(s) across accounts")
        if c.shared_ips:
            codes.append(f"CC03: {len(c.shared_ips)} shared IP address(es) across accounts")
        if c.size >= 6:
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
        print(f"  Community {c.community_id}: {c.size} accounts, "
              f"score={c.suspicion_score:.3f}, "
              f"shared_devices={len(c.shared_devices)}")
        for rc in c.reason_codes:
            print(f"    {rc}")