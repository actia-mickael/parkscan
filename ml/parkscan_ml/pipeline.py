"""Pipeline d'inférence ALPR, porté de l'ancien projet : chemins explicites, erreurs levées, pas de dessin.

Branche 1 : détection de plaque (YOLO affiné) puis lecture (fast-plate-ocr).
Branche 2 : détection du véhicule principal (YOLO COCO) puis classification de la marque (EfficientNet B0).
"""

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as functional
from fast_plate_ocr import LicensePlateRecognizer
from PIL import Image
from torchvision import transforms
from torchvision.models import efficientnet_b0
from ultralytics import YOLO

from parkscan_ml.conditions import Conditions, estimate_conditions
from parkscan_ml.logging import get_logger
from parkscan_ml.plates import normalize_plate

log = get_logger(__name__)

VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}  # classes COCO
BRAND_INPUT_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

BBox = tuple[int, int, int, int]


@dataclass(slots=True)
class PlateDetection:
    bbox: BBox
    det_conf: float
    text: str = ""
    text_norm: str = ""
    ocr_conf: float = 0.0


@dataclass(slots=True)
class VehicleDetection:
    bbox: BBox
    conf: float
    class_name: str
    roi: np.ndarray = field(repr=False)


@dataclass(slots=True)
class BrandPrediction:
    label: str
    conf: float
    top3: list[tuple[str, float]]


@dataclass(slots=True)
class InferenceResult:
    plates: list[PlateDetection]
    vehicle: VehicleDetection | None
    brand: BrandPrediction | None
    conditions: Conditions
    timings_ms: dict[str, float]
    image_size: tuple[int, int]


def file_digest(path: Path, length: int = 12) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def _clip_box(xyxy: list[float], shape: tuple[int, ...]) -> BBox:
    h, w = shape[:2]
    x1, y1, x2, y2 = (round(v) for v in xyxy)
    return max(0, x1), max(0, y1), min(w, x2), min(h, y2)


class BrandClassifier:
    """EfficientNet B0 (torchvision) à 224 px, étiquettes lues dans le checkpoint."""

    def __init__(self, path: Path, device: str) -> None:
        checkpoint = self._load_checkpoint(path, device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
            labels = [str(x) for x in checkpoint.get("label_encoder_classes", [])]
            num_classes = int(checkpoint.get("num_classes") or len(labels))
            self.details: dict[str, Any] = {
                "epoch": checkpoint.get("epoch"),
                "val_acc": checkpoint.get("val_acc"),
            }
        else:
            state_dict = checkpoint
            labels = []
            num_classes = int(state_dict["classifier.1.weight"].shape[0])
            self.details = {}
        if not num_classes:
            raise ValueError(f"checkpoint {path} : nombre de classes introuvable")
        if labels and len(labels) != num_classes:
            raise ValueError(
                f"checkpoint {path} : {len(labels)} étiquettes pour {num_classes} classes"
            )
        self.labels = labels or [f"class_{i}" for i in range(num_classes)]

        model = efficientnet_b0(weights=None)
        model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)
        model.load_state_dict(state_dict)
        self.model = model.to(device).eval()
        self.device = device
        self.transform = transforms.Compose(
            [
                transforms.Resize((BRAND_INPUT_SIZE, BRAND_INPUT_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )
        self.details.update({"arch": "efficientnet_b0", "img_size": BRAND_INPUT_SIZE})

    @staticmethod
    def _load_checkpoint(path: Path, device: str) -> Any:
        try:
            return torch.load(path, map_location=device, weights_only=True)
        except Exception:
            return torch.load(path, map_location=device, weights_only=False)

    def predict(self, roi_bgr: np.ndarray) -> BrandPrediction:
        rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
        tensor = self.transform(Image.fromarray(rgb)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = functional.softmax(self.model(tensor), dim=1)[0]
        top_probs, top_idx = torch.topk(probs, min(3, len(probs)))
        top3 = [
            (self.labels[i], float(p))
            for i, p in zip(top_idx.tolist(), top_probs.tolist(), strict=True)
        ]
        return BrandPrediction(label=top3[0][0], conf=top3[0][1], top3=top3)


class ALPRPipeline:
    def __init__(
        self,
        *,
        plate_detector_path: Path,
        vehicle_detector_path: Path,
        brand_classifier_path: Path,
        ocr_model_name: str,
        device: str = "cpu",
        torch_threads: int | None = None,
    ) -> None:
        if torch_threads:
            torch.set_num_threads(torch_threads)
        self.device = device
        started = time.perf_counter()

        self.plate_model = YOLO(str(plate_detector_path))
        self.vehicle_model = YOLO(str(vehicle_detector_path))
        self.ocr = LicensePlateRecognizer(ocr_model_name)
        self.brand = BrandClassifier(brand_classifier_path, device)

        self.versions = {
            "plate_detector": f"local:{plate_detector_path.name}:{file_digest(plate_detector_path)}",
            "vehicle_detector": vehicle_detector_path.stem,
            "ocr": ocr_model_name,
            "brand_classifier": f"local:{brand_classifier_path.name}:{file_digest(brand_classifier_path)}",
        }
        log.info(
            "pipeline_loaded",
            device=device,
            labels=len(self.brand.labels),
            seconds=round(time.perf_counter() - started, 1),
        )

    @property
    def labels(self) -> list[str]:
        return self.brand.labels

    # --- Branche 1 ---------------------------------------------------------------------------

    def detect_plates(self, img_bgr: np.ndarray, conf_threshold: float) -> list[PlateDetection]:
        results = self.plate_model.predict(
            img_bgr, conf=conf_threshold, verbose=False, device=self.device
        )
        plates: list[PlateDetection] = []
        for box in results[0].boxes:
            bbox = _clip_box(box.xyxy[0].tolist(), img_bgr.shape)
            plates.append(PlateDetection(bbox=bbox, det_conf=float(box.conf[0])))
        plates.sort(key=lambda p: p.det_conf, reverse=True)
        return plates

    def read_plate(self, roi_bgr: np.ndarray) -> tuple[str, float]:
        """Texte lu et confiance réelle (moyenne des probabilités par caractère)."""
        if roi_bgr.size == 0:
            return "", 0.0
        # Le format attendu dépend du modèle OCR chargé (les récents sont en RGB, les anciens en gris).
        color_mode = getattr(getattr(self.ocr, "config", None), "image_color_mode", "grayscale")
        code = cv2.COLOR_BGR2RGB if color_mode == "rgb" else cv2.COLOR_BGR2GRAY
        predictions = self.ocr.run(cv2.cvtColor(roi_bgr, code), return_confidence=True)
        return self._first_prediction(predictions)

    @staticmethod
    def _first_prediction(predictions: Any) -> tuple[str, float]:
        """Tolère les deux formes de retour de fast-plate-ocr : objets (plate, char_probs) ou tuple de listes."""
        text, probs = "", None
        if isinstance(predictions, tuple) and len(predictions) == 2:
            plates, all_probs = predictions
            if len(plates):
                text, probs = str(plates[0]), all_probs[0]
        elif predictions:
            first = predictions[0]
            text = str(getattr(first, "plate", first))
            probs = getattr(first, "char_probs", None)
        text = text.replace("_", "").strip()
        if not text:
            return "", 0.0
        if probs is None:
            return text, 0.0
        probs_arr = np.asarray(probs, dtype=float).ravel()[: len(text)]
        conf = float(probs_arr.mean()) if probs_arr.size else 0.0
        return text, conf

    # --- Branche 2 ---------------------------------------------------------------------------

    def detect_vehicle(self, img_bgr: np.ndarray, conf_threshold: float) -> VehicleDetection | None:
        results = self.vehicle_model.predict(
            img_bgr,
            conf=conf_threshold,
            verbose=False,
            device=self.device,
            classes=list(VEHICLE_CLASSES),
        )
        best: VehicleDetection | None = None
        best_area = 0
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            if class_id not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = _clip_box(box.xyxy[0].tolist(), img_bgr.shape)
            area = (x2 - x1) * (y2 - y1)
            if area > best_area:
                best_area = area
                best = VehicleDetection(
                    bbox=(x1, y1, x2, y2),
                    conf=float(box.conf[0]),
                    class_name=VEHICLE_CLASSES[class_id],
                    roi=img_bgr[y1:y2, x1:x2],
                )
        return best

    # --- Orchestration -----------------------------------------------------------------------

    def process(
        self,
        img_bgr: np.ndarray,
        *,
        det_threshold: float = 0.5,
        vehicle_threshold: float = 0.25,
        run_branch2: bool = True,
    ) -> InferenceResult:
        timings: dict[str, float] = {}
        started = time.perf_counter()

        def lap(name: str, since: float) -> float:
            now = time.perf_counter()
            timings[name] = round((now - since) * 1000, 1)
            return now

        t = started
        conditions = estimate_conditions(img_bgr)
        t = lap("conditions", t)

        plates = self.detect_plates(img_bgr, det_threshold)
        t = lap("plate_det", t)
        for plate in plates:
            x1, y1, x2, y2 = plate.bbox
            plate.text, plate.ocr_conf = self.read_plate(img_bgr[y1:y2, x1:x2])
            plate.text_norm = normalize_plate(plate.text)
        t = lap("ocr", t)

        vehicle = brand = None
        if run_branch2:
            vehicle = self.detect_vehicle(img_bgr, vehicle_threshold)
            t = lap("vehicle_det", t)
            if vehicle is not None and vehicle.roi.size:
                brand = self.brand.predict(vehicle.roi)
                t = lap("brand", t)

        timings["total"] = round((time.perf_counter() - started) * 1000, 1)
        return InferenceResult(
            plates=plates,
            vehicle=vehicle,
            brand=brand,
            conditions=conditions,
            timings_ms=timings,
            image_size=(img_bgr.shape[0], img_bgr.shape[1]),
        )
