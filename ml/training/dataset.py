"""Jeu de données d'une version : manifeste sur le S3, téléchargement des crops, Dataset torch."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from parkscan_ml.brand import BRAND_INPUT_SIZE, IMAGENET_MEAN, IMAGENET_STD, brand_eval_transform
from training.settings import TrainerSettings


@dataclass(slots=True)
class Sample:
    key: str
    brand: str
    split: str  # "train" | "val"
    review_id: str
    path: Path | None = None


def parse_manifest(text: str) -> list[Sample]:
    samples: list[Sample] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        samples.append(
            Sample(
                key=row["key"],
                brand=row["brand"],
                split=row.get("split", "train"),
                review_id=row.get("review_id", ""),
            )
        )
    return samples


def class_counts(samples: list[Sample], split: str | None = None) -> dict[str, int]:
    counter = Counter(s.brand for s in samples if split is None or s.split == split)
    return dict(sorted(counter.items()))


def s3_client(settings: TrainerSettings) -> Any:
    import boto3
    from botocore.config import Config

    session = boto3.session.Session(
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    return session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def fetch_manifest(client: Any, bucket: str, dataset_version: str) -> list[Sample]:
    key = f"versions/{dataset_version}/manifest.jsonl"
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return parse_manifest(body)


def download(client: Any, bucket: str, samples: list[Sample], work_dir: Path) -> list[Sample]:
    """Télécharge chaque crop dans work_dir/<split>/<marque>/<review_id>.jpg ; ignore les absents."""
    ready: list[Sample] = []
    for sample in samples:
        target = work_dir / sample.split / sample.brand / f"{sample.review_id or 'x'}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not target.is_file():
                client.download_file(bucket, sample.key, str(target))
            sample.path = target
            ready.append(sample)
        except Exception as exc:
            print(f"[dataset] crop ignoré {sample.key} : {exc}")
    return ready


def train_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(BRAND_INPUT_SIZE, scale=(0.75, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


class CropDataset(Dataset):
    """Images de véhicules étiquetées par marque ; la cible est l'indice dans `labels`."""

    def __init__(self, samples: list[Sample], labels: list[str], train: bool) -> None:
        index = {label: i for i, label in enumerate(labels)}
        self.items = [(s.path, index[s.brand]) for s in samples if s.path and s.brand in index]
        self.transform = train_transform() if train else brand_eval_transform()

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> tuple[Any, int]:
        path, target = self.items[i]
        with Image.open(path) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, target
