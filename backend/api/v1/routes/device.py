"""
Device profiling API routes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_permission


class DeviceEventRequest(BaseModel):
    """Privacy-minimised event from an authenticated bank channel."""

    account_id: str = Field(..., min_length=1, max_length=100)
    device_fingerprint_hash: str = Field(..., min_length=16, max_length=128)
    observed_at: datetime | None = None
    source_channel: str = Field("WEB", pattern="^(WEB|MOBILE|BRANCH|API)$")
    is_emulator: bool = False
    is_rooted: bool = False
    is_bot: bool = False


def register_device_routes(r: APIRouter, limiter: Limiter):
    """Register device profiling routes on the given router."""

    @r.post("/device/events", tags=["device"])
    @limiter.limit("120/minute")
    async def record_device_event(
        request: Request,
        body: DeviceEventRequest,
        _user=Depends(require_permission("onboarding:write")),
    ):
        """Record a hashed device observation from a customer-facing channel."""
        from api.deps import get_device_profiler

        observed_at = body.observed_at or datetime.now(timezone.utc)
        indicators = tuple(
            name
            for enabled, name in (
                (body.is_emulator, "emulator"),
                (body.is_rooted, "rooted"),
                (body.is_bot, "bot"),
            )
            if enabled
        )
        profiler = get_device_profiler()
        profiler.record_device_event(
            account_id=body.account_id,
            device_id=body.device_fingerprint_hash,
            timestamp=observed_at.timestamp(),
            risk_indicators=indicators,
        )
        trust = profiler.compute_trust(body.account_id)
        return success_response(
            data={
                "accepted": True,
                "account_id": body.account_id,
                "source_channel": body.source_channel,
                "device_trust_score": trust.device_trust_score,
                "reason_codes": list(trust.reason_codes),
            }
        )

    @r.get("/device/{account_id}", tags=["device"])
    @limiter.limit("30/minute")
    async def get_device_trust(
        request: Request,
        account_id: str,
        _user=Depends(require_permission("alerts:read")),
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
        _user=Depends(require_permission("alerts:read")),
    ):
        """Get aggregate device profiling statistics."""
        from api.deps import get_device_profiler

        profiler = get_device_profiler()
        return success_response(data=profiler.get_device_stats())
