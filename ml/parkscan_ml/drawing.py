"""Annotation optionnelle de l'image (débogage, back-office). Jamais utilisée par la décision d'accès."""

import base64

import cv2
import numpy as np

from parkscan_ml.pipeline import InferenceResult

GREEN = (0, 200, 0)
ORANGE = (0, 140, 255)


def annotate(img_bgr: np.ndarray, result: InferenceResult) -> np.ndarray:
    out = img_bgr.copy()
    if result.vehicle is not None:
        x1, y1, x2, y2 = result.vehicle.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), ORANGE, 2)
        label = result.vehicle.class_name
        if result.brand is not None:
            label += f" | {result.brand.label} {result.brand.conf:.2f}"
        cv2.putText(out, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ORANGE, 2)
    for plate in result.plates:
        x1, y1, x2, y2 = plate.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), GREEN, 2)
        text = f"{plate.text or '?'} {plate.ocr_conf:.2f}"
        cv2.putText(out, text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, GREEN, 2)
    return out


def encode_jpeg_b64(img_bgr: np.ndarray, quality: int = 85) -> str:
    ok, buffer = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("encodage JPEG impossible")
    return base64.b64encode(buffer.tobytes()).decode()
