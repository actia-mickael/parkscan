"""Miroir du contrat du service ML (ml/parkscan_ml/schemas.py)."""

from typing import Any

from pydantic import BaseModel


class MlPlate(BaseModel):
    bbox: list[int]
    text: str
    text_norm: str
    ocr_conf: float
    det_conf: float


class MlVehicle(BaseModel):
    bbox: list[int]
    class_name: str
    conf: float


class MlBrand(BaseModel):
    label: str
    conf: float
    top3: list[tuple[str, float]]


class MlInferResult(BaseModel):
    plates: list[MlPlate]
    vehicle: MlVehicle | None
    brand: MlBrand | None
    conditions: dict[str, Any]
    timings_ms: dict[str, float]
    model_versions: dict[str, str]
    image_size: list[int]
