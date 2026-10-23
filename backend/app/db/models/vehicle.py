"""Véhicule : une plaque rattachée à un résident. L'unicité porte sur la plaque normalisée par locataire."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "plate_norm", name="uq_vehicles_tenant_id_plate_norm"),
        Index("ix_vehicles_site_plate", "site_id", "plate_norm"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Recopié depuis le résident : la décision d'accès à la barrière se fait par site, sans jointure.
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("residents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plate_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    plate_norm: Mapped[str] = mapped_column(String(12), nullable=False)
    declared_brand: Mapped[str | None] = mapped_column(
        ForeignKey("brands.slug", ondelete="SET NULL")
    )
    declared_model: Mapped[str | None] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(30))
    access_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
