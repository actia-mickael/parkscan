"""Point d'entrée FastAPI : cycle de vie, CORS, routeurs."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_keys, auth, health, ingest, residents, sites, tenants, users, vehicles
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.app_env, settings.app_log_level)
    log = get_logger(__name__)
    log.info("startup", app=settings.app_name, env=settings.app_env, version=__version__)
    yield
    await engine.dispose()
    log.info("shutdown")


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
):
    app.include_router(router, prefix=API_PREFIX)
