from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models.passage import Decision, PassageStatus


class CaptureResponse(BaseModel):
    """Réponse à l'agent de bord : ce qu'il faut pour ouvrir ou non la barrière."""

    passage_id: UUID
    status: PassageStatus
    decision: Decision
    reason: str
    plate_text: str | None
    plate_norm: str | None
    ocr_conf: float | None
    brand: str | None
    brand_conf: float | None
    is_mismatch: bool
    latency_ms: int | None
    duplicate: bool = False  # True si la capture avait déjà été traitée (rejeu de l'agent)


class PassageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    site_id: UUID
    vehicle_id: UUID | None
    captured_at: datetime | None
    received_at: datetime
    client_request_id: str
    status: PassageStatus
    decision: Decision
    decision_reason: str
    plate_text: str | None
    plate_norm: str | None
    ocr_conf: float | None
    det_conf: float | None
    plate_bbox: list[int] | None
    vehicle_bbox: list[int] | None
    vehicle_class: str | None
    brand_pred: str | None
    brand_conf: float | None
    brand_top3: list[Any] | None
    declared_brand_snapshot: str | None
    is_mismatch: bool
    image_key: str | None
    plate_crop_key: str | None
    vehicle_crop_key: str | None
    conditions: dict[str, Any] | None
    latency_ms: int | None
    ml_latency_ms: int | None
    model_versions: dict[str, str] | None


class PassageDetail(PassageRead):
    raw_result: dict[str, Any] | None


class PresignedImage(BaseModel):
    url: str
    expires_in: int
    kind: str
