"""健康检查。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from backend import __version__

router = APIRouter(tags=["system"])


@router.get("/api/health", summary="健康检查")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "time": datetime.now(timezone.utc).isoformat(),
    }
