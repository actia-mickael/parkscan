"""Résolution des modèles : poids locaux (ML_WEIGHTS_DIR). Le registre MLflow s'y branchera (étape 7)."""

from dataclasses import dataclass
from pathlib import Path

from parkscan_ml.config import Settings
from parkscan_ml.logging import get_logger
from parkscan_ml.pipeline import ALPRPipeline

log = get_logger(__name__)


@dataclass(slots=True)
class ModelSources:
    plate_detector: Path
    vehicle_detector: Path
    brand_classifier: Path
    ocr_model: str
    origin: str


class ModelRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sources: ModelSources | None = None

    def resolve(self) -> ModelSources:
        s = self.settings
        missing = [
            str(p)
            for p in (s.plate_detector_path, s.brand_classifier_path, s.vehicle_detector_path)
            if not p.is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "poids introuvables : "
                + ", ".join(missing)
                + " (lancer `make ml-fetch-weights`, ou vérifier ML_WEIGHTS_DIR)"
            )
        return ModelSources(
            plate_detector=s.plate_detector_path,
            vehicle_detector=s.vehicle_detector_path,
            brand_classifier=s.brand_classifier_path,
            ocr_model=s.ocr_model_name,
            origin="local",
        )

    def load(self) -> ALPRPipeline:
        sources = self.resolve()
        pipeline = ALPRPipeline(
            plate_detector_path=sources.plate_detector,
            vehicle_detector_path=sources.vehicle_detector,
            brand_classifier_path=sources.brand_classifier,
            ocr_model_name=sources.ocr_model,
            device=self.settings.device,
            torch_threads=self.settings.torch_threads,
        )
        self.sources = sources
        log.info("models_resolved", origin=sources.origin, versions=pipeline.versions)
        return pipeline
