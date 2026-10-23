"""Point d'entrée de l'agent de bord (clé API) : liste blanche du site et captures."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import or_, select

from app.api.deps import ApiKeyDep, SessionDep, get_ml_client, get_rate_limiter, get_storage
from app.core.config import get_settings
from app.db.models.passage import Passage
from app.db.models.resident import Resident
from app.db.models.vehicle import Vehicle
from app.schemas.ingest import WhitelistResponse
from app.schemas.passage import CaptureResponse
from app.services.capture import CaptureInput, find_existing, process_capture
from app.services.ml_client import MlRejectedError

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


def _to_capture_response(passage: Passage, *, duplicate: bool = False) -> CaptureResponse:
    return CaptureResponse(
        passage_id=passage.id,
        status=passage.status,
        decision=passage.decision,
        reason=passage.decision_reason,
        plate_text=passage.plate_text,
        plate_norm=passage.plate_norm,
        ocr_conf=passage.ocr_conf,
        brand=passage.brand_pred,
        brand_conf=passage.brand_conf,
        is_mismatch=passage.is_mismatch,
        latency_ms=passage.latency_ms,
        duplicate=duplicate,
    )


@router.post("/capture", response_model=CaptureResponse)
async def capture(
    request: Request,
    ctx: ApiKeyDep,
    session: SessionDep,
    background: BackgroundTasks,
    image: Annotated[UploadFile, File()],
    client_request_id: Annotated[str, Form(min_length=8, max_length=64)],
    captured_at: Annotated[datetime | None, Form()] = None,
    run_brand: Annotated[str | None, Form()] = None,
) -> CaptureResponse:
    """Une capture → une décision. Rejouable : le même client_request_id renvoie le passage existant."""
    settings = get_settings()
    if not get_rate_limiter(request).allow(str(ctx.api_key.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de captures pour cette clé")

    existing = await find_existing(session, ctx.site.id, client_request_id)
    if existing is not None:
        await session.commit()
        return _to_capture_response(existing, duplicate=True)

    data = await image.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image vide")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Image trop volumineuse")

    run_brand_flag = run_brand is None or run_brand.strip().lower() in {"1", "true", "yes", "on"}
    try:
        passage = await process_capture(
            session,
            get_ml_client(request),
            get_storage(request),
            settings,
            background,
            CaptureInput(
                ctx=ctx,
                image=data,
                client_request_id=client_request_id,
                captured_at=captured_at,
                run_brand=run_brand_flag,
            ),
        )
    except MlRejectedError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Image refusée : {exc}") from exc
    return _to_capture_response(passage)
