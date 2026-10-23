"""Client HTTP sur l'application avec un pipeline simulé : aucun modèle réel n'est chargé."""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from parkscan_ml.conditions import estimate_conditions
from parkscan_ml.main import app
from parkscan_ml.pipeline import BrandPrediction, InferenceResult, PlateDetection, VehicleDetection
from parkscan_ml.registry import ModelSources


class FakePipeline:
    versions: ClassVar[dict[str, str]] = {
        "plate_detector": "fake:plate",
        "vehicle_detector": "fake:vehicle",
        "ocr": "fake:ocr",
        "brand_classifier": "fake:brand",
    }
    labels: ClassVar[list[str]] = ["peugeot", "renault"]

    class brand:  # noqa: N801 - imite l'attribut du vrai pipeline
        details: ClassVar[dict[str, str]] = {"arch": "fake"}
        labels: ClassVar[list[str]] = ["peugeot", "renault"]

    def process(
        self,
        img: np.ndarray,
        *,
        det_threshold: float,
        vehicle_threshold: float,
        run_branch2: bool,
    ) -> InferenceResult:
        h, w = img.shape[:2]
        vehicle = brand = None
        if run_branch2:
            vehicle = VehicleDetection(bbox=(0, 0, w, h), conf=0.9, class_name="car", roi=img)
            brand = BrandPrediction("renault", 0.8, [("renault", 0.8), ("peugeot", 0.2)])
        return InferenceResult(
            plates=[
                PlateDetection(
                    bbox=(10, 10, min(w, 120), min(h, 40)),
                    det_conf=det_threshold + 0.1,
                    text="AB-123-CD",
                    text_norm="AB123CD",
                    ocr_conf=0.93,
                )
            ],
            vehicle=vehicle,
            brand=brand,
            conditions=estimate_conditions(img),
            timings_ms={"total": 1.0},
            image_size=(h, w),
        )


class FakeRegistry:
    def __init__(self) -> None:
        self.sources = ModelSources(
            plate_detector="p",
            vehicle_detector="v",
            brand_classifier="b",
            ocr_model="o",
            origin="fake",
        )
        self.loads = 0

    def load(self) -> FakePipeline:
        self.loads += 1
        return FakePipeline()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app.state.lock = asyncio.Lock()
    app.state.semaphore = asyncio.Semaphore(1)
    app.state.registry = FakeRegistry()
    app.state.pipeline = FakePipeline()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
def jpeg_bytes() -> bytes:
    img = np.full((240, 320, 3), 128, dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (120, 40), (255, 255, 255), -1)
    ok, buffer = cv2.imencode(".jpg", img)
    assert ok
    return buffer.tobytes()
