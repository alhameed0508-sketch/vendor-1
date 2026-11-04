"""
MuleCatch Persistence Layer
============================
Wraps Neo4j client with fallback to in-memory store.
The API uses this abstraction — if Neo4j is available, data persists
across restarts; otherwise, an in-memory dict keeps the demo working.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PersistenceLayer:
    """Unified persistence: Neo4j when available, in-memory fallback."""

    def __init__(self):
        self._neo4j = None
        self._use_neo4j = False
        self._memory: Dict[str, Any] = {
            "alerts": [],
            "dataset": None,
            "kpi": {
                "total_alerts": 0,
                "false_positives_avoided": 0,
                "hours_saved": 0.0,
                "fraud_prevented_inr": 0.0,
                "investigation_time_reduction_pct": 75,
                "strs_filed": 0,
            },
        }
        self._try_connect_neo4j()

    def _try_connect_neo4j(self):
        import os
        import socket

        from core.config import get_settings

        settings = get_settings()

        # Quick pre-check: try TCP connect to Neo4j port before loading the driver
        # This avoids the slow driver timeout when Neo4j isn't running
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        host = neo4j_uri.split("://")[-1].split(":")[0]
        port = int(neo4j_uri.split(":")[-1].split("/")[0]) if ":" in neo4j_uri.split("://")[-1] else 7687
        try:
            sock = socket.create_connection((host, port), timeout=1)
            sock.close()
        except (OSError, ConnectionRefusedError, socket.timeout):
            if not settings.demo_mode:
                raise RuntimeError(
                    f"Neo4j unreachable at {host}:{port}. "
                    "Production requires a running Neo4j instance. "
                    "In-memory fallback is not available in production."
                )
            logger.info("Neo4j not reachable at %s:%s — using in-memory fallback", host, port)
            return
        try:
            from graph_engine.neo4j_client import Neo4jClient

            client = Neo4jClient()
            if client.verify_connectivity():
                self._neo4j = client
                self._use_neo4j = True
                logger.info("Neo4j connected — using persistent storage")
            else:
                if not settings.demo_mode:
                    raise RuntimeError("Neo4j connectivity check failed. Production requires a running Neo4j instance.")
                logger.info("Neo4j unavailable — using in-memory fallback")
        except RuntimeError:
            raise
        except Exception as exc:
            if not settings.demo_mode:
                raise RuntimeError(f"Neo4j connection failed: {exc}. Production requires a running Neo4j instance.")
            logger.info("Neo4j import/connect failed (%s) — using in-memory fallback", exc)

    @property
    def is_persistent(self) -> bool:
        return self._use_neo4j

    # ── Alert operations ──────────────────────────────────────────────────────

    def store_alerts(self, alerts: List[Dict]):
        if self._use_neo4j:
            for alert in alerts:
                self._neo4j.upsert_alert(alert)
        self._memory["alerts"] = alerts

    @staticmethod
    def _restore_alert(props: Dict) -> Dict:
        """Restore the full alert payload persisted as Neo4j JSON."""
        payload_json = props.get("payload_json")
        if not payload_json:
            return props
        try:
            restored = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            return props
        for field in ("status", "investigator_notes"):
            if field in props:
                restored[field] = props[field]
        return restored

    def get_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        if self._use_neo4j:
            rows = self._neo4j.get_alerts(severity=severity, status=status, limit=limit)
            if rows:
                return [self._restore_alert(r["props"]) for r in rows]

        # In-memory fallback
        alerts = list(self._memory["alerts"])
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity.upper()]
        if status:
            alerts = [a for a in alerts if a.get("status") == status.upper()]
        return alerts[:limit]

    def get_alert(self, alert_id: str) -> Optional[Dict]:
        if self._use_neo4j:
            result = self._neo4j.get_alert(alert_id)
            if result:
                return self._restore_alert(result)

        for a in self._memory["alerts"]:
            if a["alert_id"] == alert_id:
                return a
        return None

    def update_alert(self, alert_id: str, status: Optional[str] = None, notes: Optional[str] = None) -> Optional[Dict]:
        if self._use_neo4j:
            result = self._neo4j.update_alert_status(alert_id, status=status, notes=notes)
            if result:
                # Immutable update of in-memory copy
                self._memory["alerts"] = [
                    {
                        **a,
                        **({"status": status} if status else {}),
                        **({"investigator_notes": notes} if notes is not None else {}),
                    }
                    if a["alert_id"] == alert_id
                    else a
                    for a in self._memory["alerts"]
                ]
                return self._restore_alert(result)

        # In-memory fallback — immutable update
        updated = None
        new_alerts = []
        for a in self._memory["alerts"]:
            if a["alert_id"] == alert_id:
                updated = {
                    **a,
                    **({"status": status} if status else {}),
                    **({"investigator_notes": notes} if notes is not None else {}),
                }
                new_alerts.append(updated)
            else:
                new_alerts.append(a)
        self._memory["alerts"] = new_alerts
        return updated

    # ── KPI operations ────────────────────────────────────────────────────────

    def get_kpi(self) -> Dict:
        return dict(self._memory["kpi"])

    def update_kpi(self, **kwargs):
        self._memory["kpi"].update(kwargs)

    def increment_kpi(self, key: str, amount: float = 1):
        self._memory["kpi"][key] = self._memory["kpi"].get(key, 0) + amount

    # ── Dataset cache ─────────────────────────────────────────────────────────

    def get_dataset(self) -> Optional[Dict]:
        return self._memory["dataset"]

    def set_dataset(self, dataset: Dict):
        self._memory["dataset"] = dataset

    def clear(self):
        if self._use_neo4j:
            self._neo4j.delete_all_alerts()
        self._memory["alerts"] = []
        self._memory["dataset"] = None

    # ── Graph stats ───────────────────────────────────────────────────────────

    def get_graph_stats(self) -> Optional[Dict]:
        if self._use_neo4j:
            return self._neo4j.get_graph_stats()
        return None

    # ── Graph cross-check (onboarding) ────────────────────────────────────

    def find_flagged_neighbors(
        self,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict:
        """Check graph for flagged neighbors. Returns empty result if Neo4j unavailable."""
        if self._use_neo4j:
            try:
                return self._neo4j.find_flagged_neighbors(
                    device_id=device_id,
                    ip_address=ip_address,
                    phone=phone,
                )
            except Exception as exc:
                logger.warning("Graph cross-check failed: %s", exc)
        return {"flagged_count": 0, "flagged_accounts": [], "cluster_ids": []}

    def close(self):
        if self._neo4j:
            self._neo4j.close()
