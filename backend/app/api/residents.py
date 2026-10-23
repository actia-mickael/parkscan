"""Résidents : lecture pour tous les rôles (dans leur périmètre), écriture pour gestionnaire et admin."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUserDep, ManagerDep, SessionDep
from app.core.plates import normalize_plate
from app.db.models.resident import Resident
from app.db.models.vehicle import Vehicle
from app.schemas.common import Page
from app.schemas.resident import ResidentCreate, ResidentRead, ResidentUpdate
from app.schemas.vehicle import VehicleRead
from app.services.db import save
from app.services.residents import get_resident_in_scope
from app.services.sites import get_site_in_scope, scope_filter

router = APIRouter(prefix="/residents", tags=["residents"])


@router.get("", response_model=Page[ResidentRead])
async def list_residents(
    current: CurrentUserDep,
    session: SessionDep,
    site_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[ResidentRead]:
    stmt = scope_filter(select(Resident), Resident, current)
    if site_id is not None:
        site = await get_site_in_scope(session, current, site_id)
        stmt = stmt.where(Resident.site_id == site.id)
    if q:
        pattern = f"%{q.strip()}%"
        conditions = [Resident.last_name.ilike(pattern), Resident.first_name.ilike(pattern)]
        plate = normalize_plate(q)
        if plate:
            by_plate = select(Vehicle.resident_id).where(
                Vehicle.tenant_id == current.tenant_id, Vehicle.plate_norm.contains(plate)
            )
            conditions.append(Resident.id.in_(by_plate))
        stmt = stmt.where(or_(*conditions))

    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Resident.last_name, Resident.first_name).offset((page - 1) * size).limit(size)
    )
    return Page(
        items=[ResidentRead.model_validate(r) for r in rows], total=total, page=page, size=size
    )


@router.post("", response_model=ResidentRead, status_code=status.HTTP_201_CREATED)
async def create_resident(
    payload: ResidentCreate, current: ManagerDep, session: SessionDep
) -> Resident:
    site = await get_site_in_scope(session, current, payload.site_id)
    resident = Resident(tenant_id=site.tenant_id, **payload.model_dump())
    session.add(resident)
    await save(session, resident)
    return resident


@router.get("/{resident_id}", response_model=ResidentRead)
async def read_resident(
    resident_id: uuid.UUID, current: CurrentUserDep, session: SessionDep
) -> Resident:
    return await get_resident_in_scope(session, current, resident_id)


@router.patch("/{resident_id}", response_model=ResidentRead)
async def update_resident(
    resident_id: uuid.UUID, payload: ResidentUpdate, current: ManagerDep, session: SessionDep
) -> Resident:
    resident = await get_resident_in_scope(session, current, resident_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resident, field, value)
    await save(session, resident)
    return resident


@router.delete("/{resident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resident(resident_id: uuid.UUID, current: ManagerDep, session: SessionDep) -> None:
    resident = await get_resident_in_scope(session, current, resident_id)
    await session.delete(resident)  # les véhicules suivent (cascade en base)
    await session.commit()


@router.get("/{resident_id}/vehicles", response_model=list[VehicleRead])
async def list_resident_vehicles(
    resident_id: uuid.UUID, current: CurrentUserDep, session: SessionDep
) -> list[Vehicle]:
    resident = await get_resident_in_scope(session, current, resident_id)
    rows = await session.scalars(
        select(Vehicle).where(Vehicle.resident_id == resident.id).order_by(Vehicle.plate_norm)
    )
    return list(rows)
