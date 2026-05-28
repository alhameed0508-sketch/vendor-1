"""
Device profiling API routes.
"""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_permission


def register_device_routes(r: APIRouter, limiter: Limiter):
    """Register device profiling routes on the given router."""

    @r.get("/device/{account_id}", tags=["device"])
    @limiter.limit("30/minute")
    async def get_device_trust(
        request: Request,
        account_id: str,
        _user=Depends(require_permission("read:alerts")),
    ):
        """Get device trust score for an account."""
        from api.deps import get_device_profiler

        profiler = get_device_profiler()
        result = profiler.compute_trust(account_id)
        return success_response(
            data={
                "account_id": result.account_id,
                "device_trust_score": result.device_trust_score,
                "device_count": result.device_count,
                "recent_switches_24h": result.recent_switches_24h,
                "shared_device_accounts": list(result.shared_device_accounts),
                "reason_codes": list(result.reason_codes),
            }
        )

    @r.get("/device/stats", tags=["device"])
    @limiter.limit("30/minute")
    async def get_device_stats(
        request: Request,
        _user=Depends(require_permission("read:alerts")),
    ):
        """Get aggregate device profiling statistics."""
        from api.deps import get_device_profiler

        profiler = get_device_profiler()
        return success_response(data=profiler.get_device_stats())
