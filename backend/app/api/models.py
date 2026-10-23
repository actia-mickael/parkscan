"""Modèles servis : provenance et versions du service ML, rechargement à chaud (administrateur)."""

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import AdminDep, CurrentUserDep, get_ml_client
from app.core.logging import get_logger
from app.schemas.models import ServedModels
from app.services.ml_client import MlUnavailableError

router = APIRouter(prefix="/models", tags=["models"])
log = get_logger(__name__)


@router.get("", response_model=ServedModels)
async def served_models(request: Request, _current: CurrentUserDep) -> ServedModels:
    try:
        payload = await get_ml_client(request).models()
    except (MlUnavailableError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service ML indisponible") from exc
    return ServedModels.model_validate(payload)


@router.post("/reload", response_model=ServedModels)
async def reload_models(request: Request, current: AdminDep) -> ServedModels:
    """Re-résout les modèles (alias MLflow ou poids locaux) et les remplace sans interruption."""
    try:
        payload = await get_ml_client(request).reload()
    except (MlUnavailableError, httpx.HTTPError) as exc:
        log.warning("models_reload_failed", error=str(exc) or type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Rechargement impossible : service ML indisponible ou modèles introuvables",
        ) from exc
    log.info("models_reloaded", user_id=str(current.user.id))
    return ServedModels.model_validate(payload)
