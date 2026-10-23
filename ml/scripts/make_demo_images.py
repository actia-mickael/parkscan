"""Fabrique les images de démonstration : photos libres de droits dont la plaque réelle est remplacée
par une plaque française fictive dessinée à l'emplacement détecté par le vrai détecteur.

Aucune plaque réelle ne subsiste dans le dépôt. Usage (dans le conteneur ml) :
    python scripts/make_demo_images.py --src /tmp/demo_src --out /app/weights/demo_out
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from parkscan_ml.config import get_settings
from parkscan_ml.registry import ModelRegistry

# fichier source (préfixe) -> (nom de sortie, plaque fictive)
MAPPING = {
    "04_Citro_n_C3_1_2": ("ZA-103-ZB_citroen_c3.jpg", "ZA-103-ZB"),
    "07_Dacia_Sandero_III": ("ZA-107-ZB_dacia_sandero.jpg", "ZA-107-ZB"),
    "01_Peugeot_208": ("ZZ-999-ZZ_inconnu.jpg", "ZZ-999-ZZ"),
    "05_Citro_n_C3_Aircross": ("ZA-106-ZB_acces_desactive.jpg", "ZA-106-ZB"),
}
MAX_WIDTH = 1280
EU_BLUE = (153, 51, 0)  # BGR


def draw_plate(
    img: np.ndarray, bbox: tuple[int, int, int, int], text: str, expand: float = 0.25
) -> None:
    # La zone détectée est légèrement agrandie : la plaque dessinée reste lisible même de loin.
    x1, y1, x2, y2 = bbox
    dx, dy = int((x2 - x1) * expand / 2), int((y2 - y1) * expand / 2)
    x1, y1 = max(0, x1 - dx), max(0, y1 - dy)
    x2, y2 = min(img.shape[1], x2 + dx), min(img.shape[0], y2 + dy)
    w, h = x2 - x1, y2 - y1
    if w < 20 or h < 8:
        return
    # fond blanc légèrement cassé, bordure sombre
    cv2.rectangle(img, (x1, y1), (x2, y2), (245, 245, 240), -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), (40, 40, 40), max(1, h // 30))
    band = max(3, int(w * 0.085))
    cv2.rectangle(img, (x1, y1), (x1 + band, y2), EU_BLUE, -1)
    cv2.rectangle(img, (x2 - band, y1), (x2, y2), EU_BLUE, -1)
    # "F" dans la bande gauche
    f_scale = h / 60
    cv2.putText(
        img,
        "F",
        (x1 + band // 5, y2 - h // 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        f_scale * 0.6,
        (255, 255, 255),
        max(1, int(f_scale * 1.5)),
    )
    # texte principal, ajusté pour tenir entre les bandes
    inner_w = w - 2 * band - w // 12
    scale = h / 30
    thickness = max(2, int(scale * 2.8))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    if tw > inner_w:
        scale *= inner_w / tw
        thickness = max(2, int(scale * 2.8))
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    tx = x1 + band + (w - 2 * band - tw) // 2
    ty = y1 + (h + th) // 2
    cv2.putText(
        img, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, scale, (15, 15, 15), thickness, cv2.LINE_AA
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pipeline = ModelRegistry(get_settings()).load()
    done = 0
    for source in sorted(src.glob("*.jpg")):
        match = next((v for k, v in MAPPING.items() if source.name.startswith(k)), None)
        if match is None:
            continue
        out_name, plate_text, *rest = match
        expand = rest[0] if rest else 0.25
        img = cv2.imread(str(source))
        if img is None:
            print(f"illisible : {source.name}", file=sys.stderr)
            continue
        if img.shape[1] > MAX_WIDTH:
            ratio = MAX_WIDTH / img.shape[1]
            img = cv2.resize(
                img, (MAX_WIDTH, int(img.shape[0] * ratio)), interpolation=cv2.INTER_AREA
            )
        plates = pipeline.detect_plates(img, 0.4)
        if not plates:
            print(f"aucune plaque détectée : {source.name}", file=sys.stderr)
            continue
        draw_plate(img, plates[0].bbox, plate_text, expand)
        cv2.imwrite(str(out / out_name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        # contrôle : relecture de la plaque fictive par le pipeline complet
        result = pipeline.process(
            cv2.imread(str(out / out_name))
        )  # contrôle sur le fichier enregistré
        read = result.plates[0].text_norm if result.plates else "-"
        conf = result.plates[0].ocr_conf if result.plates else 0.0
        brand = f"{result.brand.label} {result.brand.conf:.2f}" if result.brand else "-"
        print(f"{out_name:36s} lu={read:9s} ocr={conf:.2f} marque={brand}")
        done += 1
    print(f"{done} images écrites dans {out}")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
