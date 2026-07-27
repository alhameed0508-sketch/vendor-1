"""Neo4j client wrapper for MuleCatch graph operations.

Provides full CRUD for accounts, transactions, alerts, devices, and IPs.
Connection pooling via the neo4j driver. All queries use parameterized Cypher.
"""

import os
import time
import logging
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, AuthError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thread-safe Neo4j client with connection pooling."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        max_connection_pool_size: int = 50,
        tls_enabled: bool = False,
    ):
        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.getenv("NEO4J_USER", "neo4j")
        self._password = password or os.getenv(
            "NEO4J_PASSWORD", "CHANGE_ME_NOT_FOR_PRODUCTION"
        )
        self._tls_enabled = (
            tls_enabled or os.getenv("NEO4J_TLS_ENABLED", "false").lower() == "true"
        )

        driver_kwargs = {
            "auth": (self._user, self._password),
            "max_connection_pool_size": max_connection_pool_size,
            "connection_timeout": 5,
            "connection_acquisition_timeout": 5,
        }

        if self._tls_enabled:
            driver_kwargs["encrypted"] = True

        self.driver = GraphDatabase.driver(self._uri, **driver_kwargs)

    def close(self):
        self.driver.close()

    def verify_connectivity(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except (ServiceUnavailable, AuthError) as exc:
            logger.warning("Neo4j connectivity check failed: %s", exc)
            return False

    def run_with_retry(self, query: str, max_retries: int = 3, **params) -> List[Dict]:
        """Execute a query with exponential backoff retry on transient failures."""
        for attempt in range(max_retries):
            try:
                with self.driver.session() as session:
                    return [dict(r) for r in session.run(query, **params)]
            except (ServiceUnavailable, SessionExpired) as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        "Neo4j query failed after %d retries: %s", max_retries, exc
                    )
                    raise
                wait_time = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    "Neo4j transient error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1,
                    max_retries,
                    wait_time,
                    exc,
                )
                time.sleep(wait_time)
        return []  # unreachable, satisfies type checker

    def run(self, query: str, **params) -> List[Dict]:
        return self.run_with_retry(query, max_retries=3, **params)

    # ── Account CRUD ──────────────────────────────────────────────────────────

    def create_account(self, account: Dict) -> Dict:
        result = self.run(
            """
            MERGE (a:Account {account_id: $account_id})
            SET a.upi_id       = $upi_id,
                a.bank         = $bank,
                a.city         = $city,
                a.role         = $role,
                a.high_risk    = $high_risk,
                a.account_age  = $account_age_days,
                a.kyc_status   = $kyc_status,
                a.cluster_id   = $cluster_id,
                a.avg_monthly  = $avg_monthly_txn
            RETURN a
            """,
            account_id=account["account_id"],
            upi_id=account.get("upi_id", ""),
            bank=account.get("bank", ""),
            city=account.get("city", ""),
            role=account.get("role", "UNKNOWN"),
            high_risk=account.get("high_risk", False),
            account_age_days=account.get("account_age_days", 0),
            kyc_status=account.get("kyc_status", "UNKNOWN"),
            cluster_id=account.get("cluster_id"),
            avg_monthly_txn=account.get("avg_monthly_txn", 0),
        )
        return result[0] if result else {}

    def get_account(self, account_id: str) -> Optional[Dict]:
        result = self.run(
            "MATCH (a:Account {account_id: $id}) RETURN properties(a) AS props",
            id=account_id,
        )
        return result[0]["props"] if result else None

    # ── Transaction CRUD ──────────────────────────────────────────────────────

    def create_transaction(self, txn: Dict) -> Dict:
        result = self.run(
            """
            MATCH (src:Account {account_id: $from_account}), (dst:Account {account_id: $to_account})
            MERGE (t:Transaction {txn_id: $txn_id})
            SET t.amount        = $amount,
                t.timestamp     = $timestamp,
                t.txn_type      = $txn_type,
                t.is_suspicious = $is_suspicious,
                t.pattern       = $pattern,
                t.device_id     = $device_id,
                t.ip_address    = $ip_address
            MERGE (src)-[:SENT_TO {
                txn_id:    $txn_id,
                amount:    $amount,
                timestamp: $timestamp,
                pattern:   $pattern
            }]->(dst)
            RETURN t
            """,
            from_account=txn["from_account"],
            to_account=txn["to_account"],
            txn_id=txn["txn_id"],
            amount=float(txn["amount"]),
            timestamp=txn["timestamp"],
            txn_type=txn.get("txn_type", "UPI_PUSH"),
            is_suspicious=txn.get("is_suspicious", False),
            pattern=txn.get("pattern", "NORMAL"),
            device_id=txn.get("device_id", "UNKNOWN"),
            ip_address=txn.get("ip_address", "0.0.0.0"),
        )
        return result[0] if result else {}

    # ── Device / IP linking ───────────────────────────────────────────────────

    def link_shared_device(self, account_id: str, device_id: str):
        self.run(
            """
            MATCH (a:Account {account_id: $account_id})
            MERGE (d:Device {device_id: $device_id})
            MERGE (a)-[:USES_DEVICE]->(d)
            """,
            account_id=account_id,
            device_id=device_id,
        )

    def link_shared_ip(self, account_id: str, ip_address: str):
        self.run(
            """
            MATCH (a:Account {account_id: $account_id})
            MERGE (ip:IPAddress {address: $ip_address})
            MERGE (a)-[:FROM_IP]->(ip)
            """,
            account_id=account_id,
            ip_address=ip_address,
        )

    # ── Alert CRUD ────────────────────────────────────────────────────────────

    def upsert_alert(self, alert: Dict) -> Dict:
        result = self.run(
            """
            MERGE (al:Alert {alert_id: $alert_id})
            SET al.cluster_id   = $cluster_id,
                al.severity     = $severity,
                al.confidence   = $confidence,
                al.risk_score   = $risk_score,
                al.total_amount = $total_amount,
                al.txn_count    = $txn_count,
                al.account_count = $account_count,
                al.reason_codes = $reason_codes,
                al.shared_devices = $shared_devices,
                al.shared_ips   = $shared_ips,
                al.created_at   = $created_at,
                al.status       = $status,
                al.investigator_notes = $investigator_notes,
                al.gnn_score    = $gnn_score,
                al.payload_json = $payload_json
            RETURN properties(al) AS props
            """,
            alert_id=alert["alert_id"],
            cluster_id=alert.get("cluster_id"),
            severity=alert["severity"],
            confidence=alert["confidence"],
            risk_score=alert["risk_score"],
            total_amount=alert["total_amount"],
            txn_count=alert["txn_count"],
            account_count=alert["account_count"],
            reason_codes=alert.get("reason_codes", []),
            shared_devices=alert.get("shared_devices", []),
            shared_ips=alert.get("shared_ips", []),
            created_at=alert.get("created_at", ""),
            status=alert.get("status", "OPEN"),
            investigator_notes=alert.get("investigator_notes", ""),
            gnn_score=alert.get("gnn_score"),
            payload_json=json.dumps(alert, default=str),
        )
        return result[0]["props"] if result else {}

    def get_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        where_clauses = []
        params: Dict = {"limit": limit}
        if severity:
            where_clauses.append("al.severity = $severity")
            params["severity"] = severity
        if status:
            where_clauses.append("al.status = $status")
            params["status"] = status

        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        return self.run(
            f"""
            MATCH (al:Alert)
            {where}
            RETURN properties(al) AS props
            ORDER BY al.risk_score DESC
            LIMIT $limit
            """,
            **params,
        )

    def get_alert(self, alert_id: str) -> Optional[Dict]:
        result = self.run(
            "MATCH (al:Alert {alert_id: $id}) RETURN properties(al) AS props",
            id=alert_id,
        )
        return result[0]["props"] if result else None

    def delete_all_alerts(self) -> None:
        """Remove detection alerts before replacing an uploaded dataset."""
        self.run("MATCH (al:Alert) DETACH DELETE al")

    def update_alert_status(
        self, alert_id: str, status: Optional[str] = None, notes: Optional[str] = None
    ) -> Optional[Dict]:
        sets = []
        params: Dict = {"alert_id": alert_id}
        if status is not None:
            sets.append("al.status = $status")
            params["status"] = status
        if notes is not None:
            sets.append("al.investigator_notes = $notes")
            params["notes"] = notes
        if not sets:
            return self.get_alert(alert_id)

        result = self.run(
            f"""
            MATCH (al:Alert {{alert_id: $alert_id}})
            SET {", ".join(sets)}
            RETURN properties(al) AS props
            """,
            **params,
        )
        return result[0]["props"] if result else None

    # ── Graph queries ─────────────────────────────────────────────────────────

    def get_account_subgraph(self, account_ids: List[str]) -> Dict:
        results = self.run(
            """
            MATCH (a:Account)
            WHERE a.account_id IN $ids
            OPTIONAL MATCH (a)-[r:SENT_TO]->(b:Account)
            WHERE b.account_id IN $ids
            RETURN a, r, b
            """,
            ids=account_ids,
        )
        nodes, edges = {}, []
        for row in results:
            if row.get("a"):
                nodes[row["a"]["account_id"]] = dict(row["a"])
            if row.get("b"):
                nodes[row["b"]["account_id"]] = dict(row["b"])
            if row.get("r"):
                edges.append(dict(row["r"]))
        return {"nodes": list(nodes.values()), "edges": edges}

    def get_cluster_subgraph(self, cluster_id: str) -> Dict:
        results = self.run(
            """
            MATCH (a:Account {cluster_id: $cid})
            OPTIONAL MATCH (a)-[r:SENT_TO]->(b:Account {cluster_id: $cid})
            RETURN a, r, b
            """,
            cid=cluster_id,
        )
        nodes, edges = {}, []
        for row in results:
            if row.get("a"):
                nodes[row["a"]["account_id"]] = dict(row["a"])
            if row.get("b"):
                nodes[row["b"]["account_id"]] = dict(row["b"])
            if row.get("r"):
                edges.append(dict(row["r"]))
        return {"nodes": list(nodes.values()), "edges": edges}

    def get_community_members(self, cluster_id: str) -> List[Dict]:
        return self.run(
            """
            MATCH (a:Account {cluster_id: $cid})
            RETURN properties(a) AS props
            """,
            cid=cluster_id,
        )

    def get_recent_transactions(self, limit: int = 1000) -> List[Dict]:
        return self.run(
            """
            MATCH (src:Account)-[r:SENT_TO]->(dst:Account)
            RETURN src.account_id AS from_account,
                   dst.account_id AS to_account,
                   r.txn_id       AS txn_id,
                   r.amount       AS amount,
                   r.timestamp    AS timestamp,
                   r.pattern      AS pattern,
                   r.device_id    AS device_id,
                   r.ip_address   AS ip_address
            ORDER BY r.timestamp DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    def get_graph_stats(self) -> Dict:
        result = self.run("""
            CALL { MATCH (a:Account) RETURN count(a) AS accounts }
            CALL { MATCH ()-[r:SENT_TO]->() RETURN count(r) AS txns }
            CALL { OPTIONAL MATCH (al:Alert) RETURN count(al) AS alerts }
            RETURN accounts, txns, alerts
        """)
        if result:
            row = result[0]
            return {
                "total_accounts": row["accounts"],
                "total_transactions": row["txns"],
                "total_alerts": row["alerts"],
            }
        return {"total_accounts": 0, "total_transactions": 0, "total_alerts": 0}

    # ── Batch operations ───────────────────────────────────────────────────────

    def create_transactions_batch(self, txns: List[Dict]) -> int:
        """Bulk insert transactions using UNWIND. Returns count created."""
        result = self.run(
            """
            UNWIND $txns AS t
            MATCH (src:Account {account_id: t.from_account}), (dst:Account {account_id: t.to_account})
            MERGE (txn:Transaction {txn_id: t.txn_id})
            SET txn.amount        = t.amount,
                txn.timestamp     = t.timestamp,
                txn.txn_type      = coalesce(t.txn_type, 'UPI_PUSH'),
                txn.is_suspicious = coalesce(t.is_suspicious, false),
                txn.pattern       = coalesce(t.pattern, 'NORMAL'),
                txn.device_id     = coalesce(t.device_id, 'UNKNOWN'),
                txn.ip_address    = coalesce(t.ip_address, '0.0.0.0')
            MERGE (src)-[:SENT_TO {
                txn_id:    t.txn_id,
                amount:    t.amount,
                timestamp: t.timestamp,
                pattern:   coalesce(t.pattern, 'NORMAL')
            }]->(dst)
            RETURN count(txn) AS created
            """,
            txns=txns,
        )
        return result[0]["created"] if result else 0

    def link_devices_batch(self, links: List[Dict]) -> int:
        """Bulk link accounts to devices. Each link: {account_id, device_id}."""
        result = self.run(
            """
            UNWIND $links AS link
            MATCH (a:Account {account_id: link.account_id})
            MERGE (d:Device {device_id: link.device_id})
            MERGE (a)-[:USES_DEVICE]->(d)
            RETURN count(*) AS linked
            """,
            links=links,
        )
        return result[0]["linked"] if result else 0

    def link_ips_batch(self, links: List[Dict]) -> int:
        """Bulk link accounts to IPs. Each link: {account_id, ip_address}."""
        result = self.run(
            """
            UNWIND $links AS link
            MATCH (a:Account {account_id: link.account_id})
            MERGE (ip:IPAddress {address: link.ip_address})
            MERGE (a)-[:FROM_IP]->(ip)
            RETURN count(*) AS linked
            """,
            links=links,
        )
        return result[0]["linked"] if result else 0

    # ── Cross-check queries (onboarding) ────────────────────────────────────

    def find_accounts_by_device(self, device_id: str) -> List[Dict]:
        """Find all accounts sharing a device."""
        return self.run(
            """
            MATCH (a:Account)-[:USES_DEVICE]->(d:Device {device_id: $device_id})
            RETURN a.account_id AS account_id, a.high_risk AS high_risk,
                   a.cluster_id AS cluster_id
            """,
            device_id=device_id,
        )

    def find_accounts_by_ip(self, ip_address: str) -> List[Dict]:
        """Find all accounts sharing an IP address."""
        return self.run(
            """
            MATCH (a:Account)-[:FROM_IP]->(ip:IPAddress {address: $ip_address})
            RETURN a.account_id AS account_id, a.high_risk AS high_risk,
                   a.cluster_id AS cluster_id
            """,
            ip_address=ip_address,
        )

    def find_flagged_neighbors(
        self,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict:
        """Check if device/IP overlaps with flagged mule cluster accounts.

        Returns dict with flagged_count, flagged_accounts, cluster_ids.
        """
        flagged_accounts = []
        cluster_ids = set()

        if device_id:
            rows = self.find_accounts_by_device(device_id)
            for r in rows:
                if r.get("high_risk"):
                    flagged_accounts.append(r["account_id"])
                if r.get("cluster_id"):
                    cluster_ids.add(r["cluster_id"])

        if ip_address:
            rows = self.find_accounts_by_ip(ip_address)
            for r in rows:
                if r.get("high_risk"):
                    if r["account_id"] not in flagged_accounts:
                        flagged_accounts.append(r["account_id"])
                if r.get("cluster_id"):
                    cluster_ids.add(r["cluster_id"])

        return {
            "flagged_count": len(flagged_accounts),
            "flagged_accounts": flagged_accounts,
            "cluster_ids": list(cluster_ids),
        }

    def ensure_indexes(self) -> None:
        """Create Alert indexes if they don't exist."""
        index_queries = [
            "CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (al:Alert) REQUIRE al.alert_id IS UNIQUE",
            "CREATE INDEX alert_severity IF NOT EXISTS FOR (al:Alert) ON (al.severity)",
            "CREATE INDEX alert_status IF NOT EXISTS FOR (al:Alert) ON (al.status)",
            "CREATE INDEX alert_risk_score IF NOT EXISTS FOR (al:Alert) ON (al.risk_score)",
            "CREATE CONSTRAINT watchlist_entry_id IF NOT EXISTS FOR (w:WatchlistEntry) REQUIRE w.entry_id IS UNIQUE",
            "CREATE CONSTRAINT screening_result_id IF NOT EXISTS FOR (s:ScreeningResult) REQUIRE s.result_id IS UNIQUE",
        ]
        for q in index_queries:
            try:
                self.run(q)
            except Exception as exc:
                logger.debug("Index/constraint creation skipped: %s", exc)
