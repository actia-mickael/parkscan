"""Accès aux résidents et véhicules dans le périmètre de l'utilisateur courant."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.models.brand import Brand
from app.db.models.resident import Resident
from app.db.models.vehicle import Vehicle


async def get_resident_in_scope(
    session: AsyncSession, current: CurrentUser, resident_id: uuid.UUID
) -> Resident:
    resident = await session.get(Resident, resident_id)
    if (
        resident is None
        or resident.tenant_id != current.tenant_id
        or not current.can_access_site(resident.site_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Résident introuvable")
    return resident


async def get_vehicle_in_scope(
    session: AsyncSession, current: CurrentUser, vehicle_id: uuid.UUID
) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if (
        vehicle is None
        or vehicle.tenant_id != current.tenant_id
        or not current.can_access_site(vehicle.site_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Véhicule introuvable")
    return vehicle


async def check_brand(session: AsyncSession, slug: str | None) -> None:
    if slug is None:
        return
    brand = await session.get(Brand, slug)
    if brand is None or not brand.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Marque inconnue : {slug}")
