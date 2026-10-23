from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PlateField


class VehicleCreate(BaseModel):
    resident_id: UUID
    plate: PlateField
    declared_brand: str | None = Field(default=None, max_length=40)
    declared_model: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=30)
    access_enabled: bool = True
    valid_from: date | None = None
    valid_until: date | None = None


class VehicleUpdate(BaseModel):
    plate: PlateField | None = None
    declared_brand: str | None = Field(default=None, max_length=40)
    declared_model: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=30)
    access_enabled: bool | None = None
    valid_from: date | None = None
    valid_until: date | None = None


class AccessToggle(BaseModel):
    enabled: bool


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    site_id: UUID
    resident_id: UUID
    plate_raw: str
    plate_norm: str
    declared_brand: str | None
    declared_model: str | None
    color: str | None
    access_enabled: bool
    valid_from: date | None
    valid_until: date | None
    created_at: datetime
