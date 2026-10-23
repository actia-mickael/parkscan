"""État de santé : sonde de vie (sans dépendance) et sonde complète (base de données)."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app import __version__
from app.api.deps import SessionDep
from app.core.logging import get_logger
from app.schemas.health import HealthResponse, LiveResponse

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger(__name__)


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("", response_model=HealthResponse)
async def health(session: SessionDep, response: Response) -> HealthResponse:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        log.warning("health_db_failed", error=str(exc))
        checks["db"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    if overall != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status=overall, checks=checks, version=__version__)
