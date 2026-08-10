"""Sanctions and PEP screening routes."""

from api.deps import get_screening_service
from api.v1.schemas.screening import BatchScreenRequest, ScreenAccountRequest
from core.config import get_settings
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission
from services.screening_service import ScreeningService
from slowapi import Limiter


def register_screening_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register watchlist screening endpoints."""

    @r.post("/screen")
    @limiter.limit("60/minute")
    def screen_account(
        request: Request,
        body: ScreenAccountRequest,
        _user: dict = Depends(require_permission("screening:write")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        return success_response(service.screen_account(body.account_id, body.name, body.identifiers))

    @r.post("/screen-batch")
    @limiter.limit("10/minute")
    def screen_batch(
        request: Request,
        body: BatchScreenRequest,
        _user: dict = Depends(require_permission("screening:write")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        return success_response(service.screen_accounts_batch([item.model_dump() for item in body.accounts]))

    @r.get("/results/{account_id}")
    @limiter.limit("100/minute")
    def results_for_account(
        request: Request,
        account_id: str,
        _user: dict = Depends(require_permission("screening:read")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        return success_response(service.get_results_for_account(account_id))

    @r.get("/watchlist")
    @limiter.limit("60/minute")
    def list_watchlist(
        request: Request,
        source: str | None = None,
        limit: int = 100,
        _user: dict = Depends(require_permission("screening:read")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        return success_response(service.get_entries(source=source, limit=min(max(limit, 1), 500)))

    @r.post("/watchlist/refresh-unsc")
    @limiter.limit("2/hour")
    def refresh_unsc(
        request: Request,
        _user: dict = Depends(require_permission("screening:write")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        # The URL is server-controlled to prevent this endpoint becoming an
        # authenticated server-side request forgery primitive.
        return success_response(service.refresh_unsc_list(get_settings().unsc_url))

    @r.get("/stats")
    @limiter.limit("100/minute")
    def get_stats(
        request: Request,
        _user: dict = Depends(require_permission("screening:read")),
        service: ScreeningService = Depends(get_screening_service),
    ):
        return success_response(service.get_stats())
