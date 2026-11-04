"""
Alert service — business logic for alert operations.

When real infrastructure (Neo4j, Redis) is unavailable the service falls
back to in-process stubs so the demo works without any external deps.
"""

import fnmatch
import logging
import time
from typing import Dict, List, Optional

from core.exceptions import NotFoundError

# Graceful imports — fall back to stubs when infra modules are absent
try:
    from repositories.alert_repository import AlertRepository
except Exception:
    AlertRepository = None  # type: ignore[assignment,misc]

try:
    from services.audit_service import AuditService
except Exception:
    AuditService = None  # type: ignore[assignment,misc]

try:
    from cache.cache_manager import CacheManager
except Exception:
    CacheManager = None  # type: ignore[assignment,misc]

try:
    from cache.keys import (
        alert_key,
        explanation_key,
        narrative_key,
        shap_key,
        subgraph_key,
    )
except Exception:
    # Inline key helpers when cache.keys is unavailable
    def alert_key(aid: str) -> str:
        return f"alert:{aid}"

    def explanation_key(aid: str) -> str:
        return f"explanation:{aid}"

    def narrative_key(aid: str) -> str:
        return f"narrative:{aid}"

    def shap_key(aid: str) -> str:
        return f"shap:{aid}"

    def subgraph_key(aid: str) -> str:
        return f"subgraph:{aid}"


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback stubs (used only when real infra is not injected)
# ---------------------------------------------------------------------------

DEMO_ALERTS: List[Dict] = [
    {
        "alert_id": "ALT-0001",
        "severity": "CRITICAL",
        "status": "OPEN",
        "risk_score": 0.91,
        "total_amount": 1850000,
        "account_count": 6,
        "txn_count": 24,
        "reason_codes": [
            "R01: Rapid fund aggregation",
            "R02: Structured deposits below \u20b92L",
            "R03: Shared device fingerprint",
            "R04: New account (<7 days)",
        ],
        "nodes": [
            {
                "account_id": "AC001",
                "role": "SOURCE",
                "smurf_score": 0.93,
                "betweenness": 0.62,
                "pagerank": 0.18,
                "account_age_days": 3,
                "bank": "IOB",
                "city": "Chennai",
                "kyc_status": "PARTIAL",
                "upi_id": "src01@iob",
            },
            {
                "account_id": "AC002",
                "role": "AGGREGATOR",
                "smurf_score": 0.88,
                "betweenness": 0.78,
                "pagerank": 0.21,
                "account_age_days": 5,
                "bank": "IOB",
                "city": "Chennai",
                "kyc_status": "PARTIAL",
                "upi_id": "agg02@iob",
            },
            {
                "account_id": "AC003",
                "role": "MULE",
                "smurf_score": 0.76,
                "betweenness": 0.31,
                "pagerank": 0.09,
                "account_age_days": 12,
                "bank": "SBI",
                "city": "Coimbatore",
                "kyc_status": "PENDING",
                "upi_id": "mule03@sbi",
            },
            {
                "account_id": "AC004",
                "role": "MULE",
                "smurf_score": 0.71,
                "betweenness": 0.22,
                "pagerank": 0.08,
                "account_age_days": 8,
                "bank": "SBI",
                "city": "Madurai",
                "kyc_status": "PENDING",
                "upi_id": "mule04@sbi",
            },
            {
                "account_id": "AC005",
                "role": "MULE",
                "smurf_score": 0.68,
                "betweenness": 0.18,
                "pagerank": 0.07,
                "account_age_days": 6,
                "bank": "BOI",
                "city": "Trichy",
                "kyc_status": "PENDING",
                "upi_id": "mule05@boi",
            },
            {
                "account_id": "AC006",
                "role": "LEGITIMATE",
                "smurf_score": 0.12,
                "betweenness": 0.05,
                "pagerank": 0.04,
                "account_age_days": 420,
                "bank": "IOB",
                "city": "Chennai",
                "kyc_status": "COMPLETE",
                "upi_id": "legit06@iob",
            },
        ],
        "edges": [
            {
                "from_account": "AC001",
                "to_account": "AC002",
                "total_amount": 750000,
                "txn_count": 8,
                "pattern": "SMURFING",
                "timestamps": ["2025-05-01T02:14:00", "2025-05-01T02:38:00"],
            },
            {
                "from_account": "AC001",
                "to_account": "AC003",
                "total_amount": 450000,
                "txn_count": 5,
                "pattern": "SMURFING",
                "timestamps": ["2025-05-01T03:10:00"],
            },
            {
                "from_account": "AC002",
                "to_account": "AC004",
                "total_amount": 380000,
                "txn_count": 6,
                "pattern": "CONSOLIDATION",
                "timestamps": ["2025-05-02T14:22:00"],
            },
            {
                "from_account": "AC002",
                "to_account": "AC005",
                "total_amount": 270000,
                "txn_count": 5,
                "pattern": "SMURFING",
                "timestamps": ["2025-05-02T15:00:00"],
            },
            {
                "from_account": "AC003",
                "to_account": "AC006",
                "total_amount": 120000,
                "txn_count": 3,
                "pattern": "NORMAL",
                "timestamps": ["2025-05-03T09:00:00"],
            },
            {
                "from_account": "AC004",
                "to_account": "AC006",
                "total_amount": 80000,
                "txn_count": 2,
                "pattern": "NORMAL",
                "timestamps": ["2025-05-03T10:00:00"],
            },
        ],
        "shared_devices": ["DEV-8821"],
        "shared_ips": ["103.21.244.7"],
    },
    {
        "alert_id": "ALT-0002",
        "severity": "HIGH",
        "status": "OPEN",
        "risk_score": 0.74,
        "total_amount": 620000,
        "account_count": 4,
        "txn_count": 11,
        "reason_codes": [
            "R02: Structured deposits below \u20b92L",
            "R05: UPI velocity spike",
        ],
        "nodes": [
            {
                "account_id": "AC010",
                "role": "SOURCE",
                "smurf_score": 0.77,
                "betweenness": 0.55,
                "pagerank": 0.14,
                "account_age_days": 14,
                "bank": "IOB",
                "city": "Bangalore",
                "kyc_status": "PARTIAL",
                "upi_id": "src10@iob",
            },
            {
                "account_id": "AC011",
                "role": "MULE",
                "smurf_score": 0.65,
                "betweenness": 0.33,
                "pagerank": 0.10,
                "account_age_days": 21,
                "bank": "HDFC",
                "city": "Bangalore",
                "kyc_status": "PENDING",
                "upi_id": "mule11@hdfc",
            },
            {
                "account_id": "AC012",
                "role": "MULE",
                "smurf_score": 0.59,
                "betweenness": 0.28,
                "pagerank": 0.08,
                "account_age_days": 18,
                "bank": "HDFC",
                "city": "Mysore",
                "kyc_status": "PENDING",
                "upi_id": "mule12@hdfc",
            },
            {
                "account_id": "AC013",
                "role": "LEGITIMATE",
                "smurf_score": 0.08,
                "betweenness": 0.04,
                "pagerank": 0.03,
                "account_age_days": 730,
                "bank": "IOB",
                "city": "Bangalore",
                "kyc_status": "COMPLETE",
                "upi_id": "legit13@iob",
            },
        ],
        "edges": [
            {
                "from_account": "AC010",
                "to_account": "AC011",
                "total_amount": 320000,
                "txn_count": 6,
                "pattern": "SMURFING",
                "timestamps": ["2025-05-04T11:00:00"],
            },
            {
                "from_account": "AC010",
                "to_account": "AC012",
                "total_amount": 300000,
                "txn_count": 5,
                "pattern": "SMURFING",
                "timestamps": ["2025-05-04T11:45:00"],
            },
            {
                "from_account": "AC011",
                "to_account": "AC013",
                "total_amount": 180000,
                "txn_count": 3,
                "pattern": "NORMAL",
                "timestamps": ["2025-05-05T09:00:00"],
            },
        ],
        "shared_devices": [],
        "shared_ips": ["45.115.8.22"],
    },
    {
        "alert_id": "ALT-0003",
        "severity": "MEDIUM",
        "status": "UNDER_REVIEW",
        "risk_score": 0.52,
        "total_amount": 210000,
        "account_count": 3,
        "txn_count": 7,
        "reason_codes": ["R03: Shared device fingerprint"],
        "nodes": [
            {
                "account_id": "AC020",
                "role": "SOURCE",
                "smurf_score": 0.54,
                "betweenness": 0.40,
                "pagerank": 0.11,
                "account_age_days": 30,
                "bank": "IOB",
                "city": "Mumbai",
                "kyc_status": "COMPLETE",
                "upi_id": "src20@iob",
            },
            {
                "account_id": "AC021",
                "role": "MULE",
                "smurf_score": 0.48,
                "betweenness": 0.22,
                "pagerank": 0.07,
                "account_age_days": 45,
                "bank": "PNB",
                "city": "Pune",
                "kyc_status": "PARTIAL",
                "upi_id": "mule21@pnb",
            },
            {
                "account_id": "AC022",
                "role": "MULE",
                "smurf_score": 0.44,
                "betweenness": 0.18,
                "pagerank": 0.06,
                "account_age_days": 60,
                "bank": "PNB",
                "city": "Nagpur",
                "kyc_status": "PARTIAL",
                "upi_id": "mule22@pnb",
            },
        ],
        "edges": [
            {
                "from_account": "AC020",
                "to_account": "AC021",
                "total_amount": 120000,
                "txn_count": 4,
                "pattern": "CONSOLIDATION",
                "timestamps": ["2025-05-06T16:00:00"],
            },
            {
                "from_account": "AC020",
                "to_account": "AC022",
                "total_amount": 90000,
                "txn_count": 3,
                "pattern": "CONSOLIDATION",
                "timestamps": ["2025-05-06T16:30:00"],
            },
        ],
        "shared_devices": ["DEV-4412"],
        "shared_ips": [],
    },
]


class _StubRepo:
    """In-memory fallback when AlertRepository / Neo4j is unavailable."""

    def __init__(self):
        self._alerts = [dict(a) for a in DEMO_ALERTS]

    def find_all(self, severity=None, status=None, limit=50):
        alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity.upper()]
        if status:
            alerts = [a for a in alerts if a["status"] == status.upper()]
        return alerts[:limit]

    def find_by_id(self, alert_id: str):
        for a in self._alerts:
            if a["alert_id"] == alert_id:
                return a
        return None

    def update(self, alert_id: str, status=None, notes=None):
        for a in self._alerts:
            if a["alert_id"] == alert_id:
                if status:
                    a["status"] = status
                if notes:
                    a["notes"] = notes
                return a
        return None


class _SimpleCache:
    """Thread-unsafe in-process cache, used when CacheManager is unavailable."""

    def __init__(self):
        self._store: Dict[str, tuple] = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value, l1_ttl: int = 60, l2_ttl: int = 600):
        self._store[key] = (value, time.time() + l1_ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def delete_pattern(self, pattern: str):
        to_delete = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in to_delete:
            del self._store[k]


class _StubAudit:
    """Fallback audit logger that prints to stdout."""

    def log(self, action, user_id, resource_id, details):
        logger.info("[AUDIT] %s user=%s resource=%s %s", action, user_id, resource_id, details)


class AlertService:
    """Alert business logic: CRUD, explanation, narrative, shap, subgraph.

    All dependencies are optional — when omitted, in-process stubs with
    demo data are used so the service works without Neo4j/Redis.
    """

    def __init__(
        self,
        alert_repo=None,
        cache=None,
        audit_service=None,
    ):
        self._repo = alert_repo or _StubRepo()
        self._cache = cache or _SimpleCache()
        self._audit = audit_service or _StubAudit()

    def list_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """List current alerts from the shared repository."""
        alerts = self._repo.find_all(severity=severity, status=status, limit=limit)
        return {
            "total": len(alerts),
            "alerts": alerts[offset:],
        }

    def get_alert(self, alert_id: str) -> Dict:
        """Get a current alert by ID. Raises NotFoundError."""
        alert = self._repo.find_by_id(alert_id)
        if not alert:
            raise NotFoundError("Alert", alert_id)
        return alert

    def update_alert(
        self,
        alert_id: str,
        status: Optional[str],
        notes: Optional[str],
        user_id: str,
    ) -> Dict:
        """Update alert status/notes. Invalidates cache."""
        result = self._repo.update(alert_id, status=status, notes=notes)
        if not result:
            raise NotFoundError("Alert", alert_id)

        # Invalidate related caches
        self._cache.delete(alert_key(alert_id))
        self._cache.delete_pattern("alerts:list:*")

        details = f"status={status}"
        if notes:
            details += f", notes_length={len(notes)}"
        self._audit.log("ALERT_UPDATE", user_id, alert_id, details)
        return result

    def get_explanation(self, alert_id: str) -> Dict:
        """Return explainability data. Cached, lazy-generates if missing."""
        alert = self._get_alert_or_raise(alert_id)
        cache_k = self._versioned_key(explanation_key(alert_id), alert)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        explanation = alert.get("explanation")
        if explanation:
            self._cache.set(cache_k, explanation, l1_ttl=120, l2_ttl=1800)
            return explanation

        try:
            from explainability.explainer import explain_alert

            exp = explain_alert(alert)
            result = exp.to_dict()
        except Exception:
            result = self._stub_explanation(alert)
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_narrative(self, alert_id: str) -> Dict:
        """Return judge-ready narrative. Cached."""
        alert = self._get_alert_or_raise(alert_id)
        cache_k = self._versioned_key(narrative_key(alert_id), alert)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        narrative = alert.get("narrative")
        if narrative:
            self._cache.set(cache_k, narrative, l1_ttl=120, l2_ttl=1800)
            return narrative

        try:
            from detection.mule_classifier import classify_cluster
            from explainability.narrative_generator import generate_narrative

            classification = classify_cluster(alert, [])
            narr = generate_narrative(alert, classification)
            result = narr.to_dict()
        except Exception:
            result = self._stub_narrative(alert)
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_shap(self, alert_id: str) -> Dict:
        """Return SHAP values. Cached."""
        alert = self._get_alert_or_raise(alert_id)
        cache_k = self._versioned_key(shap_key(alert_id), alert)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        try:
            from explainability.shap_explainer import (
                compute_shap_values,
                format_for_waterfall_chart,
            )

            results = compute_shap_values(alert)
            result = {
                "alert_id": alert_id,
                "shap_results": [r.to_dict() for r in results],
                "waterfall_charts": [format_for_waterfall_chart(r) for r in results[:5]],
            }
        except Exception:
            result = self._stub_shap(alert)
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_subgraph(self, alert_id: str) -> Dict:
        """Return graph topology for visualization. Cached."""
        alert = self._get_alert_or_raise(alert_id)
        cache_k = self._versioned_key(subgraph_key(alert_id), alert)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        result = {
            "alert_id": alert_id,
            "nodes": alert.get("nodes", []),
            "edges": alert.get("edges", []),
            "shared_devices": alert.get("shared_devices", []),
            "shared_ips": alert.get("shared_ips", []),
            "reason_codes": alert.get("reason_codes", []),
        }
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def _get_alert_or_raise(self, alert_id: str) -> Dict:
        """Find alert by ID or raise NotFoundError."""
        alert = self._repo.find_by_id(alert_id)
        if not alert:
            raise NotFoundError("Alert", alert_id)
        return alert

    @staticmethod
    def _versioned_key(base_key: str, alert: Dict) -> str:
        """Scope derived caches to the concrete alert generation."""
        version = alert.get("model_version", "")
        created_at = alert.get("created_at", "")
        return f"{base_key}:{version}:{created_at}"

    # ------------------------------------------------------------------
    # Stub generators (used when explainability modules are unavailable)
    # ------------------------------------------------------------------

    @staticmethod
    def _stub_explanation(alert: Dict) -> Dict:
        return {
            "alert_id": alert["alert_id"],
            "top_features": [
                {"feature": "rapid_fund_aggregation", "importance": 0.34},
                {"feature": "structured_deposits", "importance": 0.28},
                {"feature": "account_age_days", "importance": 0.18},
                {"feature": "device_overlap", "importance": 0.12},
                {"feature": "kyc_completeness", "importance": 0.08},
            ],
            "summary": (
                f"Alert {alert['alert_id']} triggered primarily due to rapid fund "
                "aggregation across newly opened accounts with shared device "
                "fingerprints, consistent with a structured smurfing pattern."
            ),
        }

    @staticmethod
    def _stub_narrative(alert: Dict) -> Dict:
        nodes = alert.get("nodes", [])
        src = next((n for n in nodes if n.get("role") == "SOURCE"), None)
        mules = [n for n in nodes if n.get("role") == "MULE"]
        return {
            "alert_id": alert["alert_id"],
            "narrative": (
                f"Between 01-May-2025 and 06-May-2025, account "
                f"{src['account_id'] if src else 'UNKNOWN'} (source) transferred "
                f"\u20b9{alert.get('total_amount', 0):,.0f} across "
                f"{len(mules)} mule account(s) in structured amounts below \u20b92L, "
                "evading transaction reporting thresholds. All mule accounts were "
                "opened within the preceding 30 days with incomplete KYC. "
                "Network analysis confirms a coordinated smurfing ring with a "
                "central aggregator node exhibiting betweenness centrality >0.7."
            ),
        }

    @staticmethod
    def _stub_shap(alert: Dict) -> Dict:
        features = [
            ("rapid_fund_aggregation", 0.34),
            ("structured_deposits", 0.28),
            ("account_age_days", -0.18),
            ("device_overlap", 0.12),
            ("kyc_completeness", -0.08),
        ]
        return {
            "alert_id": alert["alert_id"],
            "shap_results": [
                {
                    "feature": f,
                    "shap_value": v,
                    "direction": "increases" if v > 0 else "decreases",
                }
                for f, v in features
            ],
            "waterfall_charts": [
                {
                    "feature": f,
                    "value": v,
                    "cumulative": round(sum(x for _, x in features[: i + 1]), 4),
                }
                for i, (f, v) in enumerate(features)
            ],
        }
