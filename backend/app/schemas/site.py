from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    address: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="Europe/Paris", max_length=64)
    settings: dict[str, Any] = Field(default_factory=dict)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    settings: dict[str, Any] | None = None
    is_active: bool | None = None


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    address: str | None
    timezone: str
    settings: dict[str, Any]
    is_active: bool
    created_at: datetime
