"""Véhicules : recherche par plaque, création rattachée à un résident, bascule d'accès."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, ManagerDep, SessionDep
from app.core.plates import normalize_plate
from app.db.models.vehicle import Vehicle
from app.schemas.common import Page
from app.schemas.vehicle import AccessToggle, VehicleCreate, VehicleRead, VehicleUpdate
from app.services.db import save
from app.services.residents import check_brand, get_resident_in_scope, get_vehicle_in_scope
from app.services.sites import get_site_in_scope, scope_filter

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
PLATE_CONFLICT = "Cette plaque est déjà enregistrée pour ce locataire"


@router.get("", response_model=Page[VehicleRead])
async def list_vehicles(
    current: CurrentUserDep,
    session: SessionDep,
    site_id: uuid.UUID | None = None,
    resident_id: uuid.UUID | None = None,
    plate: Annotated[str | None, Query(max_length=20)] = None,
    brand: Annotated[str | None, Query(max_length=40)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[VehicleRead]:
    stmt = scope_filter(select(Vehicle), Vehicle, current)
    if site_id is not None:
        site = await get_site_in_scope(session, current, site_id)
        stmt = stmt.where(Vehicle.site_id == site.id)
    if resident_id is not None:
        stmt = stmt.where(Vehicle.resident_id == resident_id)
    if plate:
        stmt = stmt.where(Vehicle.plate_norm.contains(normalize_plate(plate)))
    if brand:
        stmt = stmt.where(Vehicle.declared_brand == brand)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Vehicle.plate_norm).offset((page - 1) * size).limit(size)
    )
    return Page(
        items=[VehicleRead.model_validate(v) for v in rows], total=total, page=page, size=size
    )


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate, current: ManagerDep, session: SessionDep
) -> Vehicle:
    resident = await get_resident_in_scope(session, current, payload.resident_id)
    await check_brand(session, payload.declared_brand)
    vehicle = Vehicle(
        tenant_id=resident.tenant_id,
        site_id=resident.site_id,
        resident_id=resident.id,
        plate_raw=payload.plate,
        plate_norm=normalize_plate(payload.plate),
        declared_brand=payload.declared_brand,
        declared_model=payload.declared_model,
        color=payload.color,
        access_enabled=payload.access_enabled,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )
    session.add(vehicle)
    await save(session, vehicle, conflict=PLATE_CONFLICT)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def read_vehicle(
    vehicle_id: uuid.UUID, current: CurrentUserDep, session: SessionDep
) -> Vehicle:
    return await get_vehicle_in_scope(session, current, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: uuid.UUID, payload: VehicleUpdate, current: ManagerDep, session: SessionDep
) -> Vehicle:
    vehicle = await get_vehicle_in_scope(session, current, vehicle_id)
    changes = payload.model_dump(exclude_unset=True)
    if "declared_brand" in changes:
        await check_brand(session, changes["declared_brand"])
    plate = changes.pop("plate", None)
    if plate is not None:
        vehicle.plate_raw = plate
        vehicle.plate_norm = normalize_plate(plate)
    for field, value in changes.items():
        setattr(vehicle, field, value)
    await save(session, vehicle, conflict=PLATE_CONFLICT)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: uuid.UUID, current: ManagerDep, session: SessionDep) -> None:
    vehicle = await get_vehicle_in_scope(session, current, vehicle_id)
    await session.delete(vehicle)
    await session.commit()


@router.post("/{vehicle_id}/access", response_model=VehicleRead)
async def toggle_access(
    vehicle_id: uuid.UUID, payload: AccessToggle, current: ManagerDep, session: SessionDep
) -> Vehicle:
    vehicle = await get_vehicle_in_scope(session, current, vehicle_id)
    vehicle.access_enabled = payload.enabled
    await save(session, vehicle)
    return vehicle
