from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.models.user import UserRole
from app.schemas.common import EmailField
from app.schemas.tenant import TenantSummary


class LoginRequest(BaseModel):
    email: EmailField
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: UserRole
    tenant: TenantSummary
    site_ids: list[UUID]
