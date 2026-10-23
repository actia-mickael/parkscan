"""Le locataire courant : lecture et réglages (administrateur)."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, SessionDep
from app.db.models.tenant import Tenant
from app.schemas.tenant import TenantRead, TenantUpdate
from app.services.db import save

router = APIRouter(prefix="/tenants", tags=["tenants"])


async def _current_tenant(session: SessionDep, current: AdminDep) -> Tenant:
    tenant = await session.get(Tenant, current.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Locataire introuvable")
    return tenant


@router.get("/me", response_model=TenantRead)
async def read_me(current: AdminDep, session: SessionDep) -> Tenant:
    return await _current_tenant(session, current)


@router.patch("/me", response_model=TenantRead)
async def update_me(payload: TenantUpdate, current: AdminDep, session: SessionDep) -> Tenant:
    tenant = await _current_tenant(session, current)
    if payload.name is not None:
        tenant.name = payload.name
    if payload.settings is not None:
        tenant.settings = payload.settings
    await save(session, tenant)
    return tenant
