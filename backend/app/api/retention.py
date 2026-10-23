"""Rétention : exécution à la demande (jeton interne : Airflow, Makefile) et simulation."""

from fastapi import APIRouter, Request

from app.api.deps import InternalDep, SessionDep, get_storage
from app.core.config import get_settings
from app.schemas.retention import RetentionReportRead
from app.services.retention import run_retention

router = APIRouter(prefix="/retention", tags=["retention"])


@router.post("/run", response_model=RetentionReportRead)
async def run(
    request: Request, _: InternalDep, session: SessionDep, dry_run: bool = False
) -> RetentionReportRead:
    """Purge les images et anonymise les plaques au-delà de la rétention ; `dry_run` compte sans agir."""
    report = await run_retention(session, get_storage(request), get_settings(), dry_run=dry_run)
    return RetentionReportRead(**report.as_dict())
