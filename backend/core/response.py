"""
Consistent API response envelope helpers.
All API responses use this format for uniformity.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.responses import JSONResponse


def success_response(data: Any, status_code: int = 200) -> JSONResponse:
    """Wrap data in a success envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def paginated_response(
    items: list,
    total: int,
    limit: int,
    offset: int,
    status_code: int = 200,
) -> JSONResponse:
    """Wrap paginated results in a success envelope with metadata."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": items,
            "error": None,
            "meta": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "count": len(items),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def error_response(
    code: str,
    message: str,
    status_code: int = 500,
    details: Optional[str] = None,
) -> JSONResponse:
    """Wrap error information in the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
