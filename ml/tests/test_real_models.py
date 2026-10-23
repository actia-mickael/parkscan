"""Tests sur les vrais modèles : exécutés seulement si les poids et des images de démo sont présents."""

import cv2
import pytest

from parkscan_ml.config import get_settings
from parkscan_ml.registry import ModelRegistry

DEMO_DIR = get_settings().demo_images_dir
settings = get_settings()
weights_present = (
    settings.plate_detector_path.is_file() and settings.brand_classifier_path.is_file()
)
demo_images = sorted(DEMO_DIR.glob("*.jpg")) if DEMO_DIR.is_dir() else []

pytestmark = pytest.mark.skipif(
    not (weights_present and demo_images), reason="poids ou images de démo absents"
)


@pytest.fixture(scope="module")
def pipeline():
    return ModelRegistry(settings).load()


def test_real_pipeline_reads_a_plate_on_demo_images(pipeline) -> None:
    found = 0
    for path in demo_images:
        img = cv2.imread(str(path))
        assert img is not None, path
        result = pipeline.process(img)
        assert result.timings_ms["total"] > 0
        if result.plates and result.plates[0].text_norm:
            found += 1
            assert 0.0 < result.plates[0].ocr_conf <= 1.0
    assert found >= 1, "aucune plaque lue sur les images de démo"
