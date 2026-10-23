"""Télécharge au build de l'image les modèles génériques : YOLO véhicule (COCO) et OCR.

Rien n'est téléchargé à l'exécution : un conteneur démarre sans accès internet.
"""

import os
from pathlib import Path

from parkscan_ml.config import get_settings


def main() -> None:
    settings = get_settings()
    settings.generic_models_dir.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO

    cwd = Path.cwd()
    os.chdir(
        settings.generic_models_dir
    )  # ultralytics enregistre les poids dans le dossier courant
    try:
        YOLO(settings.vehicle_detector_name)
    finally:
        os.chdir(cwd)
    assert settings.vehicle_detector_path.is_file(), settings.vehicle_detector_path

    from fast_plate_ocr import LicensePlateRecognizer

    LicensePlateRecognizer(settings.ocr_model_name)
    print(f"[prefetch] {settings.vehicle_detector_path} et OCR {settings.ocr_model_name} prêts")


if __name__ == "__main__":
    main()
