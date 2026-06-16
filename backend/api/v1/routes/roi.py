"""
ROI dashboard data endpoints — monthly trends and detection breakdown.
Reads from PostgreSQL tables when available, returns empty lists otherwise.
"""

import logging
from fastapi import APIRouter, Depends
from slowapi import Limiter

from core.response import success_response

logger = logging.getLogger(__name__)


def register_roi_routes(router: APIRouter, limiter: Limiter) -> None:

    @router.get("")
    def roi_summary():
        """Combined ROI data: trends + breakdown in one call."""
        trends = _get_monthly_trends()
        breakdown = _get_detection_breakdown()
        return success_response({
            "monthly_trends": trends,
            "detection_breakdown": breakdown,
        })

    @router.get("/monthly-trends")
    def monthly_trends():
        """Monthly alert/prevention/hours trend data for ROI charts."""
        return success_response(_get_monthly_trends())

    @router.get("/detection-breakdown")
    def detection_breakdown():
        """Detection pattern breakdown for ROI dashboard."""
        return success_response(_get_detection_breakdown())


def _get_monthly_trends():
    """Query monthly_trends table if PG is available."""
    try:
        from api.deps import _get_pg_engine
        engine = _get_pg_engine()
        if engine is not None:
            from infra.database.postgres import monthly_trends
            with engine.connect() as conn:
                rows = conn.execute(
                    monthly_trends.select().order_by(monthly_trends.c.month)
                ).fetchall()
            if rows:
                return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("Failed to query monthly_trends: %s", exc)
    return []


def _get_detection_breakdown():
    """Query detection_breakdown table if PG is available."""
    try:
        from api.deps import _get_pg_engine
        engine = _get_pg_engine()
        if engine is not None:
            from infra.database.postgres import detection_breakdown
            with engine.connect() as conn:
                rows = conn.execute(
                    detection_breakdown.select()
                    .order_by(detection_breakdown.c.count.desc())
                ).fetchall()
            if rows:
                return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("Failed to query detection_breakdown: %s", exc)
    return []
