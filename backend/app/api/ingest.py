"""Point d'entrée de l'agent de bord (clé API) : liste blanche du site, puis captures (étape 4)."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Response, status
from sqlalchemy import or_, select

from app.api.deps import ApiKeyDep, SessionDep
from app.db.models.resident import Resident
from app.db.models.vehicle import Vehicle
from app.schemas.ingest import WhitelistResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/whitelist", response_model=WhitelistResponse)
async def whitelist(
    ctx: ApiKeyDep,
    session: SessionDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> WhitelistResponse | Response:
    """Plaques autorisées sur le site de la clé, pour le cache local de l'agent (mode dégradé).

    Renvoie 304 si l'ETag fourni correspond : l'agent peut interroger souvent sans coût.
    """
    now = datetime.now(UTC)
    today = now.date()
    stmt = (
        select(Vehicle.plate_norm)
        .join(Resident, Resident.id == Vehicle.resident_id)
        .where(
            Vehicle.site_id == ctx.site.id,
            Vehicle.access_enabled.is_(True),
            Resident.is_active.is_(True),
            or_(Vehicle.valid_from.is_(None), Vehicle.valid_from <= today),
            or_(Vehicle.valid_until.is_(None), Vehicle.valid_until >= today),
        )
        .order_by(Vehicle.plate_norm)
    )
    plates = list(await session.scalars(stmt))
    await session.commit()  # horodatage d'usage de la clé

    etag = '"' + hashlib.sha256("\n".join(plates).encode()).hexdigest()[:32] + '"'
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return WhitelistResponse(site_id=ctx.site.id, generated_at=now, etag=etag, plates=plates)
