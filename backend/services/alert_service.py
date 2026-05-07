"""
Alert service — business logic for alert operations.
"""

from typing import Dict, List, Optional

from core.exceptions import NotFoundError
from repositories.alert_repository import AlertRepository
from services.audit_service import AuditService
from cache.cache_manager import CacheManager
from cache.keys import (
    alert_key,
    alerts_list_key,
    explanation_key,
    narrative_key,
    shap_key,
    subgraph_key,
)


class AlertService:
    """Alert business logic: CRUD, explanation, narrative, shap, subgraph."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        cache: CacheManager,
        audit_service: AuditService,
    ):
        self._repo = alert_repo
        self._cache = cache
        self._audit = audit_service

    def list_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        """List alerts with optional filters. Cache-first."""
        cache_k = alerts_list_key(severity, status, limit)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alerts = self._repo.find_all(severity=severity, status=status, limit=limit)
        result = {
            "total": len(alerts),
            "alerts": alerts[offset:],
        }
        self._cache.set(cache_k, result, l1_ttl=30, l2_ttl=300)
        return result

    def get_alert(self, alert_id: str) -> Dict:
        """Get a single alert by ID. Raises NotFoundError."""
        cache_k = alert_key(alert_id)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alert = self._repo.find_by_id(alert_id)
        if not alert:
            raise NotFoundError("Alert", alert_id)
        self._cache.set(cache_k, alert, l1_ttl=60, l2_ttl=600)
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
        cache_k = explanation_key(alert_id)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alert = self._get_alert_or_raise(alert_id)
        explanation = alert.get("explanation")
        if explanation:
            self._cache.set(cache_k, explanation, l1_ttl=120, l2_ttl=1800)
            return explanation

        from explainability.explainer import explain_alert
        exp = explain_alert(alert)
        result = exp.to_dict()
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_narrative(self, alert_id: str) -> Dict:
        """Return judge-ready narrative. Cached."""
        cache_k = narrative_key(alert_id)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alert = self._get_alert_or_raise(alert_id)
        narrative = alert.get("narrative")
        if narrative:
            self._cache.set(cache_k, narrative, l1_ttl=120, l2_ttl=1800)
            return narrative

        from explainability.narrative_generator import generate_narrative
        from detection.mule_classifier import classify_cluster
        classification = classify_cluster(alert, [])
        narr = generate_narrative(alert, classification)
        result = narr.to_dict()
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_shap(self, alert_id: str) -> Dict:
        """Return SHAP values. Cached."""
        cache_k = shap_key(alert_id)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alert = self._get_alert_or_raise(alert_id)

        from explainability.shap_explainer import compute_shap_values, format_for_waterfall_chart
        results = compute_shap_values(alert)
        result = {
            "alert_id": alert_id,
            "shap_results": [r.to_dict() for r in results],
            "waterfall_charts": [format_for_waterfall_chart(r) for r in results[:5]],
        }
        self._cache.set(cache_k, result, l1_ttl=120, l2_ttl=1800)
        return result

    def get_subgraph(self, alert_id: str) -> Dict:
        """Return graph topology for visualization. Cached."""
        cache_k = subgraph_key(alert_id)
        cached = self._cache.get(cache_k)
        if cached is not None:
            return cached

        alert = self._get_alert_or_raise(alert_id)
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
