"""Décision d'accès à la barrière : liste blanche du site, et rien d'autre."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.passage import Decision
from app.db.models.resident import Resident
from app.db.models.vehicle import Vehicle


@dataclass(slots=True)
class AccessOutcome:
    decision: Decision
    reason: str
    vehicle: Vehicle | None


async def decide(
    session: AsyncSession, site_id: uuid.UUID, plate_norm: str | None, today: date
) -> AccessOutcome:
    if not plate_norm:
        return AccessOutcome(Decision.denied, "no_plate_read", None)
    row = (
        await session.execute(
            select(Vehicle, Resident.is_active)
            .join(Resident, Resident.id == Vehicle.resident_id)
            .where(Vehicle.site_id == site_id, Vehicle.plate_norm == plate_norm)
        )
    ).first()
    if row is None:
        return AccessOutcome(Decision.denied, "unknown_plate", None)
    vehicle, resident_active = row
    if not resident_active:
        return AccessOutcome(Decision.denied, "resident_inactive", vehicle)
    if not vehicle.access_enabled:
        return AccessOutcome(Decision.denied, "access_disabled", vehicle)
    if (vehicle.valid_from and today < vehicle.valid_from) or (
        vehicle.valid_until and today > vehicle.valid_until
    ):
        return AccessOutcome(Decision.denied, "out_of_validity", vehicle)
    return AccessOutcome(Decision.allowed, "whitelist_match", vehicle)
