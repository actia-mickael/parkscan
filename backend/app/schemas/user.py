from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.user import User, UserRole
from app.schemas.common import EmailField


class UserCreate(BaseModel):
    email: EmailField
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    role: UserRole
    site_ids: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserSitesUpdate(BaseModel):
    site_ids: list[UUID]


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    site_ids: list[UUID]
    created_at: datetime

    @classmethod
    def from_model(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            site_ids=[s.id for s in user.sites],
            created_at=user.created_at,
        )
