"""Clés API des sites : création (secret affiché une seule fois), liste, révocation."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ManagerDep, SessionDep
from app.core.security import generate_api_key
from app.db.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.db import save
from app.services.sites import get_site_in_scope

router = APIRouter(tags=["api-keys"])


@router.get("/sites/{site_id}/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(
    site_id: uuid.UUID, current: ManagerDep, session: SessionDep
) -> list[ApiKey]:
    site = await get_site_in_scope(session, current, site_id)
    result = await session.scalars(
        select(ApiKey).where(ApiKey.site_id == site.id).order_by(ApiKey.created_at.desc())
    )
    return list(result)


@router.post(
    "/sites/{site_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    site_id: uuid.UUID, payload: ApiKeyCreate, current: ManagerDep, session: SessionDep
) -> ApiKeyCreated:
    site = await get_site_in_scope(session, current, site_id)
    secret, prefix, digest = generate_api_key()
    api_key = ApiKey(
        tenant_id=site.tenant_id,
        site_id=site.id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=digest,
        expires_at=payload.expires_at,
        created_by=current.user.id,
    )
    session.add(api_key)
    await save(session, api_key)
    return ApiKeyCreated(**ApiKeyRead.model_validate(api_key).model_dump(), secret=secret)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, current: ManagerDep, session: SessionDep) -> None:
    api_key = await session.get(ApiKey, key_id)
    if api_key is None or api_key.tenant_id != current.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clé introuvable")
    await get_site_in_scope(session, current, api_key.site_id)
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        await session.commit()
