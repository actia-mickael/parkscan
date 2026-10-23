from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import EmailField


class ResidentCreate(BaseModel):
    site_id: UUID
    last_name: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=80)
    email: EmailField | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)
    subscription: bool = False
    notes: str | None = None


class ResidentUpdate(BaseModel):
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    email: EmailField | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)
    subscription: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class ResidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    site_id: UUID
    last_name: str
    first_name: str
    email: str | None
    phone: str | None
    address: str | None
    city: str | None
    postal_code: str | None
    subscription: bool
    is_active: bool
    notes: str | None
    created_at: datetime
