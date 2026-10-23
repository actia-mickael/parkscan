"""Seuils et réglages effectifs : site > locataire > défauts."""

from dataclasses import dataclass, field, fields
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class EffectiveSettings:
    detection_threshold: float = 0.5
    ocr_threshold: float = 0.6
    brand_threshold: float = 0.7
    vehicle_threshold: float = 0.25
    min_dataset_size: int = field(default_factory=lambda: get_settings().min_dataset_size)
    retention_days: int = field(default_factory=lambda: get_settings().retention_days)


def resolve(
    tenant_settings: dict[str, Any] | None, site_settings: dict[str, Any] | None
) -> EffectiveSettings:
    merged: dict[str, Any] = {}
    for source in (tenant_settings or {}, site_settings or {}):
        for f in fields(EffectiveSettings):
            if f.name in source and source[f.name] is not None:
                merged[f.name] = (
                    f.type(source[f.name]) if isinstance(f.type, type) else source[f.name]
                )
    return EffectiveSettings(**merged)
