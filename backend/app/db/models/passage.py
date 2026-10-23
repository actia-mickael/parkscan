"""Passage : une capture à la barrière = exactement une ligne, quelle que soit l'issue."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PassageStatus(enum.StrEnum):
    ok = "ok"
    no_plate = "no_plate"
    low_ocr_conf = "low_ocr_conf"
    ml_error = "ml_error"


class Decision(enum.StrEnum):
    allowed = "allowed"
    denied = "denied"


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Passage(Base):
    __tablename__ = "passages"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "client_request_id", name="uq_passages_site_id_client_request_id"
        ),
        Index("ix_passages_tenant_site_received", "tenant_id", "site_id", "received_at"),
        Index(
            "ix_passages_mismatch", "tenant_id", postgresql_where=text("is_mismatch"), unique=False
        ),
        Index(
            "ix_passages_failed", "tenant_id", postgresql_where=text("status <> 'ok'"), unique=False
        ),
    )

    # Identifiant généré côté application : les clés de stockage en dépendent avant l'insertion.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    client_request_id: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[PassageStatus] = mapped_column(
        _enum(PassageStatus, "passage_status"), nullable=False
    )
    decision: Mapped[Decision] = mapped_column(_enum(Decision, "passage_decision"), nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(40), nullable=False)

    plate_text: Mapped[str | None] = mapped_column(String(20))
    plate_norm: Mapped[str | None] = mapped_column(String(12), index=True)
    ocr_conf: Mapped[float | None] = mapped_column(Float)
    det_conf: Mapped[float | None] = mapped_column(Float)
    plate_bbox: Mapped[list[int] | None] = mapped_column(JSONB)

    vehicle_bbox: Mapped[list[int] | None] = mapped_column(JSONB)
    vehicle_class: Mapped[str | None] = mapped_column(String(20))
    brand_pred: Mapped[str | None] = mapped_column(String(40))
    brand_conf: Mapped[float | None] = mapped_column(Float)
    brand_top3: Mapped[list[Any] | None] = mapped_column(JSONB)
    declared_brand_snapshot: Mapped[str | None] = mapped_column(String(40))
    is_mismatch: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)

    image_key: Mapped[str | None] = mapped_column(String(255))
    plate_crop_key: Mapped[str | None] = mapped_column(String(255))
    vehicle_crop_key: Mapped[str | None] = mapped_column(String(255))

    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    ml_latency_ms: Mapped[int | None] = mapped_column(Integer)
    model_versions: Mapped[dict[str, str] | None] = mapped_column(JSONB)

    # Rétention (ADR-011) : images supprimées, plaque remplacée par un haché
    images_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
