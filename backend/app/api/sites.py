"""Sites (parkings) du locataire. Lecture filtrée par les droits, écriture réservée à l'administrateur."""

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import AdminDep, CurrentUserDep, SessionDep
from app.core.slug import slugify
from app.db.models.site import Site
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services.db import save
from app.services.sites import get_site_in_scope

router = APIRouter(prefix="/sites", tags=["sites"])
SLUG_CONFLICT = "Un site porte déjà cet identifiant"


@router.get("", response_model=list[SiteRead])
async def list_sites(current: CurrentUserDep, session: SessionDep) -> list[Site]:
    stmt = select(Site).where(Site.tenant_id == current.tenant_id).order_by(Site.name)
    if current.allowed_site_ids is not None:
        stmt = stmt.where(Site.id.in_(current.allowed_site_ids))
    return list(await session.scalars(stmt))


@router.post("", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreate, current: AdminDep, session: SessionDep) -> Site:
    site = Site(
        tenant_id=current.tenant_id,
        name=payload.name,
        slug=payload.slug or slugify(payload.name, fallback="site"),
        address=payload.address,
        timezone=payload.timezone,
        settings=payload.settings,
    )
    session.add(site)
    await save(session, site, conflict=SLUG_CONFLICT)
    return site


@router.get("/{site_id}", response_model=SiteRead)
async def read_site(site_id: uuid.UUID, current: CurrentUserDep, session: SessionDep) -> Site:
    return await get_site_in_scope(session, current, site_id)


@router.patch("/{site_id}", response_model=SiteRead)
async def update_site(
    site_id: uuid.UUID, payload: SiteUpdate, current: AdminDep, session: SessionDep
) -> Site:
    site = await get_site_in_scope(session, current, site_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    await save(session, site, conflict=SLUG_CONFLICT)
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: uuid.UUID, current: AdminDep, session: SessionDep) -> None:
    site = await get_site_in_scope(session, current, site_id)
    await session.delete(site)
    await session.commit()
