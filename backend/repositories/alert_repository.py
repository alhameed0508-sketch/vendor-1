"""
Alert repository — data access layer for alerts.
Delegates to PersistenceLayer; no business logic here.
"""

from typing import Dict, List, Optional

from cache.redis_client import RedisClient
from graph_engine.persistence import PersistenceLayer
from repositories.cache_keys import ALERTS_CACHE_KEY


class AlertRepository:
    """Encapsulates alert data access behind a consistent interface."""

    def __init__(
        self,
        persistence: PersistenceLayer,
        redis_client: Optional[RedisClient] = None,
    ):
        self._persistence = persistence
        self._redis = redis_client

    def _get_shared(self) -> Optional[List[Dict]]:
        if self._redis is None:
            return None
        shared = self._redis.get(ALERTS_CACHE_KEY)
        return shared if isinstance(shared, list) else None

    def find_all(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch alerts with optional server-side filtering."""
        alerts = self._get_shared()
        if alerts is None:
            return self._persistence.get_alerts(
                severity=severity,
                status=status,
                limit=limit,
            )
        if severity:
            alerts = [alert for alert in alerts if alert.get("severity") == severity.upper()]
        if status:
            alerts = [alert for alert in alerts if alert.get("status") == status.upper()]
        return alerts[:limit]

    def find_by_id(self, alert_id: str) -> Optional[Dict]:
        """Fetch a single alert by ID."""
        shared = self._get_shared()
        if shared is not None:
            return next(
                (alert for alert in shared if alert.get("alert_id") == alert_id),
                None,
            )
        return self._persistence.get_alert(alert_id)

    def store_batch(self, alerts: List[Dict]) -> None:
        """Persist a batch of alert dicts."""
        self._persistence.store_alerts(alerts)
        if self._redis is not None:
            self._redis.set(ALERTS_CACHE_KEY, alerts, ttl=None)

    def update(
        self,
        alert_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update an alert's status/notes. Returns updated alert or None."""
        persisted = self._persistence.update_alert(
            alert_id,
            status=status,
            notes=notes,
        )
        shared = self._get_shared()
        cached_update = None
        if shared is not None:
            updated_alerts = []
            for alert in shared:
                if alert.get("alert_id") == alert_id:
                    cached_update = {
                        **alert,
                        **({"status": status} if status else {}),
                        **({"investigator_notes": notes} if notes is not None else {}),
                    }
                    updated_alerts.append(cached_update)
                else:
                    updated_alerts.append(alert)
            if self._redis is not None:
                self._redis.set(ALERTS_CACHE_KEY, updated_alerts, ttl=None)
        return cached_update or persisted
