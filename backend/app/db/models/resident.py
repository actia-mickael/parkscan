"""Résident : une personne rattachée à un site, propriétaire d'un ou plusieurs véhicules."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Resident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "residents"
    __table_args__ = (
        Index("ix_residents_tenant_site_last_name", "tenant_id", "site_id", "last_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=False
    )
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    subscription: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    # Un résident inactif n'ouvre plus la barrière, quels que soient ses véhicules.
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
