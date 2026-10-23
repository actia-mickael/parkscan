"""Contrat HTTP du service ML (miroir côté backend : app/services/ml_client.py)."""

from typing import Literal

from pydantic import BaseModel, Field

BBox = tuple[int, int, int, int]


class PlateOut(BaseModel):
    bbox: BBox
    text: str
    text_norm: str
    ocr_conf: float
    det_conf: float


class VehicleOut(BaseModel):
    bbox: BBox
    class_name: str
    conf: float


class BrandOut(BaseModel):
    label: str
    conf: float
    top3: list[tuple[str, float]]


class ConditionsOut(BaseModel):
    brightness: float
    lighting: str
    blur_score: float
    blur: str


class InferResponse(BaseModel):
    plates: list[PlateOut]
    vehicle: VehicleOut | None
    brand: BrandOut | None
    conditions: ConditionsOut
    timings_ms: dict[str, float]
    model_versions: dict[str, str]
    image_size: tuple[int, int] = Field(description="(hauteur, largeur)")
    annotated_image_b64: str | None = None


class ModelInfo(BaseModel):
    source: str
    version: str
    details: dict[str, str | int | float | None] = Field(default_factory=dict)


class ModelsResponse(BaseModel):
    device: str
    models: dict[str, ModelInfo]
    labels: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok", "loading", "error"]
    version: str
    device: str
    model_versions: dict[str, str]
