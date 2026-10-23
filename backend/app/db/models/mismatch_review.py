"""Écart de marque à valider : alimente le jeu d'entraînement après revue humaine."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewStatus(enum.StrEnum):
    pending = "pending"
    validated = "validated"
    rejected = "rejected"
    exported = "exported"


class ReviewOutcome(enum.StrEnum):
    predicted_correct = "predicted_correct"
    declared_correct = "declared_correct"
    custom = "custom"
    rejected = "rejected"


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class MismatchReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mismatch_reviews"
    __table_args__ = (
        Index("ix_mismatch_reviews_tenant_status", "tenant_id", "status", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    passage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("passages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    predicted_brand: Mapped[str] = mapped_column(String(40), nullable=False)
    predicted_conf: Mapped[float] = mapped_column(Float, nullable=False)
    declared_brand: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus, "review_status"), nullable=False, default=ReviewStatus.pending
    )
    outcome: Mapped[ReviewOutcome | None] = mapped_column(_enum(ReviewOutcome, "review_outcome"))
    final_brand: Mapped[str | None] = mapped_column(String(40))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)

    # Crop du véhicule à l'origine de l'écart, puis sa copie dans le dataset une fois validé.
    source_crop_key: Mapped[str | None] = mapped_column(String(255))
    dataset_key: Mapped[str | None] = mapped_column(String(255))
    dataset_version: Mapped[str | None] = mapped_column(String(40))
