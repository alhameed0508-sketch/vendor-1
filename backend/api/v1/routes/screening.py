"""
Screening routes — /api/v1/screening/*
"""
import csv
import io
from typing import List

from fastapi import APIRouter, Depends, Request, UploadFile, File
from slowapi import Limiter
from pydantic import BaseModel, Field

from core.config import get_settings
from core.response import success_response
from middleware.auth import require_permission, require_role
from api.deps import get_screening_service, get_screening_repository
from services.screening_service import ScreeningService

router = APIRouter(prefix="/screening", tags=["screening"])


def register_screening_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register screening routes on the given router."""

    @r.get("/screening/account/{account_id}")
    @limiter.limit("100/minute")
    def screen_account(
        request: Request,
        account_id: str,
        name: str,
        user: dict = Depends(require_permission("screening:read")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """Screen a single account against watchlists."""
        result = screening_svc.screen_account(account_id=account_id, name=name)
        return success_response(result)

    @r.post("/screening/batch")
    @limiter.limit("100/minute")
    def screen_batch(
        request: Request,
        accounts: List[dict],
        user: dict = Depends(require_permission("screening:read")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """Screen multiple accounts against watchlists."""
        results = screening_svc.screen_accounts_batch(accounts)
        return success_response({"results": results, "total": len(results)})

    @r.get("/screening/watchlist")
    @limiter.limit("100/minute")
    def list_watchlist(
        request: Request,
        source: str = None,
        limit: int = 100,
        user: dict = Depends(require_permission("screening:read")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """List watchlist entries (paginated)."""
        from api.deps import get_screening_repository
        repo = get_screening_repository()
        entries = repo.get_entries(source=source, limit=limit)
        return success_response({"entries": entries, "total": len(entries)})

    @r.post("/screening/watchlist/import")
    @limiter.limit("5/minute")
    def import_watchlist(
        request: Request,
        file: UploadFile = File(...),
        source: str = "CUSTOM",
        user: dict = Depends(require_role("ADMIN")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """Upload CSV watchlist (ADMIN only)."""
        content = file.file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        result = screening_svc.import_csv(rows, source=source)
        return success_response(result)

    @r.post("/screening/watchlist/refresh-unsc")
    @limiter.limit("5/minute")
    def refresh_unsc(
        request: Request,
        user: dict = Depends(require_role("ADMIN")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """Trigger UNSC sanctions list refresh (ADMIN only)."""
        settings = get_settings()
        result = screening_svc.refresh_unsc_list(settings.unsc_url)
        return success_response(result)

    @r.get("/screening/stats")
    @limiter.limit("100/minute")
    def screening_stats(
        request: Request,
        user: dict = Depends(require_permission("screening:read")),
        screening_svc: ScreeningService = Depends(get_screening_service),
    ):
        """Screening statistics."""
        return success_response(screening_svc.get_stats())
