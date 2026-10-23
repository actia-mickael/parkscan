"""Métriques exprimées sur les noms de classes : comparables entre deux modèles aux étiquettes différentes."""

import json
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader


def metrics_from_names(
    truth: list[str], top3: list[list[str]], loss: float | None = None
) -> dict[str, float]:
    """Exactitude, top 3 et F1 macro sur les classes présentes dans la vérité terrain."""
    if not truth:
        return {"accuracy": 0.0, "top3_accuracy": 0.0, "f1_macro": 0.0, "loss": loss or 0.0}
    pred = [p[0] if p else "" for p in top3]
    accuracy = sum(t == p for t, p in zip(truth, pred, strict=True)) / len(truth)
    top3_acc = sum(t in p for t, p in zip(truth, top3, strict=True)) / len(truth)
    f1s = []
    for cls in sorted(set(truth)):
        tp = sum(1 for t, p in zip(truth, pred, strict=True) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(truth, pred, strict=True) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(truth, pred, strict=True) if t == cls and p != cls)
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    result = {
        "accuracy": round(accuracy, 4),
        "top3_accuracy": round(top3_acc, 4),
        "f1_macro": round(sum(f1s) / len(f1s), 4),
    }
    if loss is not None:
        result["loss"] = round(loss, 4)
    return result


def confusion(truth: list[str], pred: list[str], classes: list[str]) -> list[list[int]]:
    index = {c: i for i, c in enumerate(classes)}
    matrix = [[0] * len(classes) for _ in classes]
    for t, p in zip(truth, pred, strict=True):
        if t in index and p in index:
            matrix[index[t]][index[p]] += 1
    return matrix


def confusion_png(matrix: list[list[int]], classes: list[str], path: Path, cell: int = 28) -> None:
    """Carte de chaleur minimaliste (Pillow) : lignes = vérité, colonnes = prédiction."""
    n = len(classes)
    margin = 110
    size = margin + n * cell + 10
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    peak = max((v for row in matrix for v in row), default=1) or 1
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            shade = int(255 - 200 * value / peak)
            x, y = margin + j * cell, margin + i * cell
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(shade, shade, 255))
            if value:
                draw.text((x + 4, y + 8), str(value), fill="black")
    for i, name in enumerate(classes):
        draw.text((4, margin + i * cell + 8), name[:16], fill="black")
        draw.text((margin + i * cell + 2, 4 + (i % 2) * 14), name[:8], fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@torch.no_grad()
def predict_names(
    model: torch.nn.Module, loader: DataLoader, labels: list[str], device: str
) -> tuple[list[str], list[list[str]], float]:
    """Vérité terrain et top 3 prédits (en noms), perte moyenne. `labels` : étiquettes du loader."""
    model.eval()
    criterion = torch.nn.CrossEntropyLoss()
    model_labels: list[str] = getattr(model, "parkscan_labels", labels)
    truth: list[str] = []
    top3: list[list[str]] = []
    total_loss, batches = 0.0, 0
    for images, targets in loader:
        logits = model(images.to(device))
        if len(model_labels) == len(labels):
            total_loss += float(criterion(logits, targets.to(device)))
            batches += 1
        k = min(3, logits.shape[1])
        for target, idx in zip(
            targets.tolist(), torch.topk(logits, k, dim=1).indices.tolist(), strict=True
        ):
            truth.append(labels[target])
            top3.append([model_labels[i] for i in idx])
    return truth, top3, (total_loss / batches if batches else 0.0)
