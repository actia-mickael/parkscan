"""Entraînement : manifeste, sélection des étiquettes, extension de la tête, métriques (sans réseau)."""

from pathlib import Path

import pytest
import torch
from PIL import Image
from torch.utils.data import DataLoader

from parkscan_ml.brand import build_brand_model
from training import dataset as ds
from training.evaluate import confusion, confusion_png, metrics_from_names, predict_names
from training.model import extend_head, set_backbone_trainable, snapshot
from training.train_brand import select_labels

MANIFEST = """
{"key": "labeled/dacia/a.jpg", "brand": "dacia", "split": "train", "review_id": "a"}
{"key": "labeled/dacia/b.jpg", "brand": "dacia", "split": "val", "review_id": "b"}
{"key": "labeled/renault/c.jpg", "brand": "renault", "split": "train", "review_id": "c"}
"""


def test_parse_manifest_and_counts() -> None:
    samples = ds.parse_manifest(MANIFEST)
    assert [s.review_id for s in samples] == ["a", "b", "c"]
    assert ds.class_counts(samples) == {"dacia": 2, "renault": 1}
    assert ds.class_counts(samples, split="train") == {"dacia": 1, "renault": 1}


def test_select_labels_adds_only_well_represented_brands() -> None:
    labels, dropped = select_labels(
        ["peugeot", "renault"], {"renault": 3, "dacia": 20, "saab": 2}, 20
    )
    assert labels == ["peugeot", "renault", "dacia"]
    assert dropped == {"saab": 2}


def test_extend_head_copies_known_classes_and_freeze() -> None:
    model = build_brand_model(2)
    old_weight = model.classifier[1].weight.detach().clone()
    extended = extend_head(model, ["peugeot", "renault"], ["peugeot", "renault", "dacia"])
    assert extended.classifier[1].out_features == 3
    assert torch.equal(extended.classifier[1].weight[1], old_weight[1])
    assert extended.parkscan_labels == ["peugeot", "renault", "dacia"]
    set_backbone_trainable(extended, False)
    assert all(not p.requires_grad for p in extended.features.parameters())
    assert all(p.requires_grad for p in extended.classifier.parameters())
    copy = snapshot(extended)
    extended.classifier[1].weight.data.zero_()
    assert not torch.equal(copy["classifier.1.weight"], extended.classifier[1].weight)


def test_metrics_from_names() -> None:
    truth = ["dacia", "dacia", "renault", "peugeot"]
    top3 = [
        ["dacia", "x", "y"],
        ["renault", "dacia", "y"],
        ["renault", "x", "y"],
        ["dacia", "x", "y"],
    ]
    metrics = metrics_from_names(truth, top3, loss=0.5)
    assert metrics["accuracy"] == 0.5
    assert metrics["top3_accuracy"] == 0.75
    # F1 : dacia 0,5 (tp1 fp1 fn1), renault 2/3 (tp1 fp1 fn0), peugeot 0 (fn1)
    assert abs(metrics["f1_macro"] - (0.5 + 2 / 3 + 0) / 3) < 1e-3
    assert metrics["loss"] == 0.5
    matrix = confusion(truth, [p[0] for p in top3], ["dacia", "peugeot", "renault"])
    assert matrix == [[1, 0, 1], [1, 0, 0], [0, 0, 1]]


def test_dataset_and_prediction_on_tiny_images(tmp_path: Path) -> None:
    samples = ds.parse_manifest(MANIFEST)
    for sample in samples:
        path = tmp_path / sample.split / sample.brand / f"{sample.review_id}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 48), (120, 30, 30)).save(path)
        sample.path = path
    labels = ["dacia", "renault"]
    loader = DataLoader(ds.CropDataset(samples, labels, train=False), batch_size=2)
    model = build_brand_model(2)
    model.parkscan_labels = labels
    truth, top3, loss = predict_names(model, loader, labels, "cpu")
    assert truth == ["dacia", "dacia", "renault"]
    assert all(len(p) == 2 and set(p) == set(labels) for p in top3)
    assert loss > 0
    confusion_png([[1, 0], [0, 1]], labels, tmp_path / "cm.png")
    assert (tmp_path / "cm.png").stat().st_size > 0


class _NoReference:
    def get_object(self, **_: object) -> dict:
        raise RuntimeError("NoSuchKey")


class _WithReference:
    def get_object(self, **kwargs: object) -> dict:
        assert kwargs["Key"] == "reference/manifest.jsonl"
        body = b'{"key": "reference/bmw/x3_0001.jpg", "brand": "bmw", "split": "val", "review_id": "ref-bmw-x3_0001"}\n'
        return {"Body": __import__("io").BytesIO(body)}


def test_fetch_reference_is_optional() -> None:
    assert ds.fetch_reference(_NoReference(), "bucket", "reference") == []
    assert ds.fetch_reference(_WithReference(), "bucket", "") == []
    samples = ds.fetch_reference(_WithReference(), "bucket", "reference/")
    assert [(s.brand, s.split, s.review_id) for s in samples] == [("bmw", "val", "ref-bmw-x3_0001")]


def test_seed_reference_selection_is_deterministic(tmp_path: Path) -> None:
    from training.seed_reference import encode, select

    files = []
    for i in range(6):
        path = tmp_path / f"clio_{i:04d}.jpg"
        Image.new("RGB", (900, 600), (i * 20, 60, 90)).save(path)
        files.append(path)
    first = select(files, 4, seed=7)
    assert first == select(list(reversed(files)), 4, seed=7) and len(first) == 4
    (tmp_path / "clio_0099.jpg").write_bytes(b"pas une image")
    with pytest.raises(Exception):  # noqa: B017 - Pillow lève UnidentifiedImageError (sous-classe d'OSError)
        encode(tmp_path / "clio_0099.jpg", max_side=512)
    data = encode(first[0], max_side=512)
    with Image.open(__import__("io").BytesIO(data)) as image:
        assert max(image.size) == 512 and image.mode == "RGB"
