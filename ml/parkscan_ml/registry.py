"""Résolution des modèles : registre MLflow par alias (« production ») avec repli sur les poids locaux.

- ML_MODEL_SOURCE=auto (défaut) : MLflow si ML_MLFLOW_TRACKING_URI est défini et joignable, sinon
  les poids de ML_WEIGHTS_DIR ;
- ML_MODEL_SOURCE=mlflow : MLflow obligatoire (le chargement échoue sinon) ;
- ML_MODEL_SOURCE=local : poids locaux seulement.

Les artefacts téléchargés sont mis en cache par version (ML_MLFLOW_CACHE_DIR/<modèle>/v<n>) : un
redémarrage ou un rechargement ne retélécharge rien tant que l'alias pointe sur la même version.
Le détecteur de véhicule et le modèle OCR, génériques, viennent toujours de l'image (prefetch).
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parkscan_ml.config import Settings
from parkscan_ml.logging import get_logger
from parkscan_ml.pipeline import ALPRPipeline

log = get_logger(__name__)

BRAND_CHECKPOINT = "checkpoint.pth"
PLATE_WEIGHTS = "plate_detector.pt"
MARKER = ".complete"


@dataclass(slots=True)
class ModelSources:
    plate_detector: Path
    vehicle_detector: Path
    brand_classifier: Path
    ocr_model: str
    origin: str  # "local" ou "mlflow"
    labels: dict[str, str] = field(default_factory=dict)  # préfixe de version par modèle
    details: dict[str, dict[str, str]] = field(default_factory=dict)  # alias, version, run…


class ModelRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sources: ModelSources | None = None

    # --- Résolution --------------------------------------------------------------------------

    def resolve(self) -> ModelSources:
        s = self.settings
        if s.model_source == "local":
            return self._resolve_local()
        if not s.mlflow_tracking_uri:
            if s.model_source == "mlflow":
                raise RuntimeError("ML_MODEL_SOURCE=mlflow exige ML_MLFLOW_TRACKING_URI")
            return self._resolve_local()
        try:
            return self._resolve_mlflow()
        except Exception as exc:
            if s.model_source == "mlflow":
                raise
            log.warning(
                "mlflow_unavailable_fallback_local",
                tracking_uri=s.mlflow_tracking_uri,
                error=str(exc) or type(exc).__name__,
            )
            return self._resolve_local()

    def _resolve_local(self) -> ModelSources:
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

    def _resolve_mlflow(self) -> ModelSources:
        s = self.settings
        if not s.vehicle_detector_path.is_file():
            raise FileNotFoundError(f"détecteur de véhicule absent : {s.vehicle_detector_path}")
        client = self._mlflow_client()
        plate_dir, plate_info = self._fetch(client, s.mlflow_plate_model)
        brand_dir, brand_info = self._fetch(client, s.mlflow_brand_model)
        return ModelSources(
            plate_detector=_find(plate_dir, PLATE_WEIGHTS),
            vehicle_detector=s.vehicle_detector_path,
            brand_classifier=_find(brand_dir, BRAND_CHECKPOINT),
            ocr_model=s.ocr_model_name,
            origin="mlflow",
            labels={
                "plate_detector": f"mlflow:{s.mlflow_plate_model}@{s.mlflow_alias}:v{plate_info['version']}",
                "brand_classifier": f"mlflow:{s.mlflow_brand_model}@{s.mlflow_alias}:v{brand_info['version']}",
            },
            details={"plate_detector": plate_info, "brand_classifier": brand_info},
        )

    def _fetch(self, client: Any, name: str) -> tuple[Path, dict[str, str]]:
        """Dossier local des artefacts de la version pointée par l'alias (téléchargée si absente)."""
        s = self.settings
        version = client.get_model_version_by_alias(name, s.mlflow_alias)
        target = s.mlflow_cache_dir / name / f"v{version.version}"
        info = {
            "registry": "mlflow",
            "name": name,
            "alias": s.mlflow_alias,
            "version": str(version.version),
            "run_id": str(version.run_id or ""),
            "source": str(version.source or ""),
        }
        marker = target / MARKER
        if marker.is_file():
            return target, info
        target.mkdir(parents=True, exist_ok=True)
        self._download(f"models:/{name}/{version.version}", target)
        marker.write_text(json.dumps(info), encoding="utf-8")
        log.info("mlflow_model_downloaded", name=name, version=version.version, path=str(target))
        return target, info

    # --- Accès à MLflow (isolés pour pouvoir les simuler dans les tests) ------------------------

    def _mlflow_client(self) -> Any:
        s = self.settings
        # Échec rapide si MLflow est injoignable : le repli local ne doit pas attendre des minutes
        # (par défaut le client réessaie 7 fois avec attente exponentielle).
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", str(s.mlflow_timeout_s))
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
        import mlflow
        from mlflow import MlflowClient

        # Le téléchargement d'un URI `models:/…` lit les adresses globales du processus (sans elles,
        # MLflow 3 retombe sur une base sqlite locale et refuse le registre) : on les fixe ici.
        mlflow.set_tracking_uri(s.mlflow_tracking_uri)
        mlflow.set_registry_uri(s.mlflow_tracking_uri)
        return MlflowClient(tracking_uri=s.mlflow_tracking_uri, registry_uri=s.mlflow_tracking_uri)

    def _download(self, artifact_uri: str, target: Path) -> None:
        import mlflow.artifacts

        mlflow.artifacts.download_artifacts(
            artifact_uri=artifact_uri,
            dst_path=str(target),
            tracking_uri=self.settings.mlflow_tracking_uri,
            registry_uri=self.settings.mlflow_tracking_uri,
        )

    # --- Chargement --------------------------------------------------------------------------

    def load(self) -> ALPRPipeline:
        sources = self.resolve()
        pipeline = ALPRPipeline(
            plate_detector_path=sources.plate_detector,
            vehicle_detector_path=sources.vehicle_detector,
            brand_classifier_path=sources.brand_classifier,
            ocr_model_name=sources.ocr_model,
            device=self.settings.device,
            torch_threads=self.settings.torch_threads,
            plate_label=sources.labels.get("plate_detector"),
            brand_label=sources.labels.get("brand_classifier"),
        )
        self.sources = sources
        log.info("models_resolved", origin=sources.origin, versions=pipeline.versions)
        return pipeline


def _find(root: Path, filename: str) -> Path:
    found = next((p for p in sorted(root.rglob(filename)) if p.is_file()), None)
    if found is None:
        raise FileNotFoundError(f"artefact {filename} absent sous {root}")
    return found
