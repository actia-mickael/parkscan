"""Point d'entrée FastAPI : cycle de vie, CORS, routeurs."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    api_keys,
    auth,
    dashboard,
    health,
    ingest,
    mismatches,
    models,
    passages,
    residents,
    retention,
    sites,
    tenants,
    training,
    users,
    vehicles,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import TokenBucketLimiter
from app.db.session import SessionLocal, engine
from app.services.ml_client import MlClient
from app.services.retention import run_retention
from app.services.storage import S3Storage

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.app_env, settings.app_log_level)
    log = get_logger(__name__)
    app.state.ml_client = MlClient(settings)
    app.state.storage = S3Storage(settings)
    app.state.rate_limiter = TokenBucketLimiter(settings.ingest_rate_per_minute)
    log.info("startup", app=settings.app_name, env=settings.app_env, version=__version__)
    retention_task = None
    if settings.retention_interval_hours > 0 and settings.app_env != "test":
        retention_task = asyncio.create_task(_retention_loop(app))
    yield
    if retention_task is not None:
        retention_task.cancel()
    await app.state.ml_client.aclose()
    await engine.dispose()
    log.info("shutdown")


async def _retention_loop(app: FastAPI) -> None:
    """Rétention périodique (ADR-011) : un premier passage peu après le démarrage, puis à intervalle."""
    log = get_logger(__name__)
    interval = settings.retention_interval_hours * 3600
    await asyncio.sleep(min(interval, 120))
    while True:
        try:
            async with SessionLocal() as session:
                await run_retention(session, app.state.storage, settings)
        except Exception:
            log.exception("retention_failed")
        await asyncio.sleep(interval)


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for router in (
    health.router,
    auth.router,
    tenants.router,
    users.router,
    sites.router,
    api_keys.router,
    residents.router,
    vehicles.router,
    ingest.router,
    passages.router,
    mismatches.router,
    models.router,
    training.router,
    retention.router,
    dashboard.router,
):
    app.include_router(router, prefix=API_PREFIX)
