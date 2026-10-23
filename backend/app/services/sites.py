"""Accès aux sites dans le périmètre de l'utilisateur courant."""

import uuid
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.models.site import Site


def _not_found() -> HTTPException:
    # Un site hors périmètre est traité comme inexistant : on ne révèle pas ce qui appartient aux autres.
    return HTTPException(status.HTTP_404_NOT_FOUND, "Site introuvable")


async def get_site_in_scope(
    session: AsyncSession, current: CurrentUser, site_id: uuid.UUID
) -> Site:
    site = await session.get(Site, site_id)
    if site is None or site.tenant_id != current.tenant_id or not current.can_access_site(site.id):
        raise _not_found()
    return site


async def load_tenant_sites(
    session: AsyncSession, tenant_id: uuid.UUID, site_ids: Iterable[uuid.UUID]
) -> list[Site]:
    """Charge des sites du locataire ; un identifiant inconnu ou étranger lève 404."""
    wanted = set(site_ids)
    if not wanted:
        return []
    result = await session.scalars(
        select(Site).where(Site.tenant_id == tenant_id, Site.id.in_(wanted))
    )
    sites = list(result)
    if len(sites) != len(wanted):
        raise _not_found()
    return sites
