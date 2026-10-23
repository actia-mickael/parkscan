"""API du service ML : inférence, santé, modèles chargés, rechargement atomique."""

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from parkscan_ml import __version__
from parkscan_ml.config import get_settings
from parkscan_ml.drawing import annotate, encode_jpeg_b64
from parkscan_ml.logging import configure_logging, get_logger
from parkscan_ml.pipeline import ALPRPipeline, InferenceResult
from parkscan_ml.registry import ModelRegistry
from parkscan_ml.schemas import (
    BrandOut,
    ConditionsOut,
    HealthResponse,
    InferResponse,
    ModelInfo,
    ModelsResponse,
    PlateOut,
    VehicleOut,
)

settings = get_settings()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.app_env, settings.log_level)
    app.state.lock = asyncio.Lock()
    app.state.semaphore = asyncio.Semaphore(settings.max_concurrency)
    app.state.registry = ModelRegistry(settings)
    app.state.pipeline = None
    try:
        app.state.pipeline = await run_in_threadpool(app.state.registry.load)
    except Exception:
        # Le service démarre quand même : /health le signale, /models/reload permet de réessayer.
        log.exception("models_load_failed")
    yield


app = FastAPI(title="ParkScan ML", version=__version__, lifespan=lifespan)


TRUE_VALUES = {"1", "true", "yes", "on"}


def _flag(value: str | None, *, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in TRUE_VALUES


def _pipeline(request: Request) -> ALPRPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Modèles non chargés")
    return pipeline


def _to_response(
    result: InferenceResult, versions: dict[str, str], annotated: str | None
) -> InferResponse:
    return InferResponse(
        plates=[
            PlateOut(
                bbox=p.bbox,
                text=p.text,
                text_norm=p.text_norm,
                ocr_conf=round(p.ocr_conf, 4),
                det_conf=round(p.det_conf, 4),
            )
            for p in result.plates
        ],
        vehicle=(
            VehicleOut(
                bbox=result.vehicle.bbox,
                class_name=result.vehicle.class_name,
                conf=round(result.vehicle.conf, 4),
            )
            if result.vehicle
            else None
        ),
        brand=(
            BrandOut(
                label=result.brand.label,
                conf=round(result.brand.conf, 4),
                top3=[(label, round(p, 4)) for label, p in result.brand.top3],
            )
            if result.brand
            else None
        ),
        conditions=ConditionsOut(**result.conditions.as_dict()),
        timings_ms=result.timings_ms,
        model_versions=versions,
        image_size=result.image_size,
        annotated_image_b64=annotated,
    )


@app.post("/infer", response_model=InferResponse)
async def infer(
    request: Request,
    image: Annotated[UploadFile, File()],
    det_threshold: Annotated[float, Form(ge=0.05, le=0.95)] = settings.detection_threshold,
    vehicle_threshold: Annotated[float, Form(ge=0.05, le=0.95)] = settings.vehicle_threshold,
    run_branch2: Annotated[str | None, Form()] = None,
    return_annotated: Annotated[str | None, Form()] = None,
) -> InferResponse:
    # Drapeaux reçus en texte : un champ absent prend sa valeur par défaut, sans dépendre du
    # traitement des booléens de formulaire par FastAPI.
    branch2 = _flag(run_branch2, default=True)
    want_annotated = _flag(return_annotated, default=False)
    pipeline = _pipeline(request)
    data = await image.read()
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Image trop volumineuse")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image illisible")

    async with request.app.state.semaphore:
        result = await run_in_threadpool(
            pipeline.process,
            img,
            det_threshold=det_threshold,
            vehicle_threshold=vehicle_threshold,
            run_branch2=branch2,
        )
    annotated = encode_jpeg_b64(annotate(img, result)) if want_annotated else None
    log.info(
        "infer",
        plates=[p.text_norm for p in result.plates],
        brand=result.brand.label if result.brand else None,
        total_ms=result.timings_ms.get("total"),
    )
    return _to_response(result, pipeline.versions, annotated)


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Modèles non chargés")
    return HealthResponse(
        status="ok", version=__version__, device=settings.device, model_versions=pipeline.versions
    )


@app.get("/models", response_model=ModelsResponse)
async def models(request: Request) -> ModelsResponse:
    pipeline = _pipeline(request)
    origin = (
        request.app.state.registry.sources.origin if request.app.state.registry.sources else "?"
    )
    infos = {
        name: ModelInfo(source=origin, version=version)
        for name, version in pipeline.versions.items()
    }
    infos["brand_classifier"].details = dict(pipeline.brand.details)
    return ModelsResponse(device=settings.device, models=infos, labels=pipeline.labels)


@app.post("/models/reload", response_model=ModelsResponse)
async def reload_models(
    request: Request, x_internal_token: Annotated[str | None, Header()] = None
) -> ModelsResponse:
    if x_internal_token is None or not secrets.compare_digest(
        x_internal_token, settings.internal_token
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton interne invalide")
    async with request.app.state.lock:
        try:
            new_pipeline = await run_in_threadpool(request.app.state.registry.load)
        except Exception as exc:
            log.exception("models_reload_failed")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
        request.app.state.pipeline = new_pipeline  # l'ancien reste servi jusqu'à cette ligne
    return await models(request)
