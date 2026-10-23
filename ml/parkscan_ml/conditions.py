"""Conditions de prise de vue : luminosité moyenne et netteté (variance du laplacien)."""

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class Conditions:
    brightness: float
    lighting: str
    blur_score: float
    blur: str

    def as_dict(self) -> dict[str, float | str]:
        return asdict(self)


def estimate_conditions(img_bgr: np.ndarray) -> Conditions:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    if brightness < 60:
        lighting = "night"
    elif brightness < 100:
        lighting = "low"
    elif brightness < 160:
        lighting = "medium"
    else:
        lighting = "day"

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < 100:
        blur = "high"
    elif blur_score < 500:
        blur = "medium"
    else:
        blur = "sharp"
    return Conditions(brightness=brightness, lighting=lighting, blur_score=blur_score, blur=blur)
