import cv2
import numpy as np

from parkscan_ml.conditions import estimate_conditions
from parkscan_ml.pipeline import ALPRPipeline, _clip_box
from parkscan_ml.plates import normalize_plate


def test_normalize_plate_matches_backend_rule() -> None:
    assert normalize_plate("ab-123 cd") == "AB123CD"
    assert normalize_plate("51-A 77.529") == "51A77529"


def test_conditions_distinguish_dark_and_bright_sharp_and_blurred() -> None:
    dark = np.full((100, 100, 3), 20, dtype=np.uint8)
    assert estimate_conditions(dark).lighting == "night"

    rng = np.random.default_rng(0)
    noisy = rng.integers(0, 255, size=(100, 100, 3), dtype=np.uint8)
    sharp = estimate_conditions(noisy)
    assert sharp.lighting in {"medium", "low"}
    assert sharp.blur == "sharp"

    blurred = cv2.GaussianBlur(noisy, (31, 31), 0)
    assert estimate_conditions(blurred).blur_score < sharp.blur_score


def test_clip_box_stays_inside_image() -> None:
    assert _clip_box([-5.2, 3.7, 500.0, 90.0], (100, 200, 3)) == (0, 4, 200, 90)


def test_first_prediction_tolerates_both_ocr_return_shapes() -> None:
    class Pred:
        plate = "AB123CD__"
        char_probs = np.array([0.9, 0.9, 0.8, 0.8, 0.8, 0.9, 0.9, 0.1, 0.1])

    text, conf = ALPRPipeline._first_prediction([Pred()])
    assert text == "AB123CD"
    assert abs(conf - np.mean([0.9, 0.9, 0.8, 0.8, 0.8, 0.9, 0.9])) < 1e-6

    text, conf = ALPRPipeline._first_prediction((["XY-9"], [np.array([1.0, 1.0, 0.5, 0.5])]))
    assert text == "XY-9"
    assert conf == 0.75

    assert ALPRPipeline._first_prediction([]) == ("", 0.0)
