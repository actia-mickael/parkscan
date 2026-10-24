"""Importe un jeu de référence multi-marques dans le bucket du jeu de données (préfixe `reference/`).

Usage (via `make mlops-seed-reference SRC=<dossier>`), dans l'image trainer :
    python -m training.seed_reference --source /opt/reference [--per-brand 50] [--val-ratio 0.2]

Le dossier source contient un sous-dossier par marque (nom = étiquette du classifieur), rempli de
photos de véhicules. Pour chaque marque, un échantillon déterministe (graine) est ré-encodé en JPEG
(métadonnées retirées, côté max limité) et envoyé sous `reference/<marque>/<nom>.jpg`, avec un
manifeste `reference/manifest.jsonl` (train/val figé) et un résumé. Les fichiers illisibles sont
ignorés (on puise dans la réserve). Idempotent : un objet déjà présent n'est pas renvoyé, sauf --force.

Ce jeu est fusionné à chaque entraînement avec les écarts validés : le modèle garde toutes les
marques, et la promotion est jugée sur un jeu de validation qui les couvre toutes (ADR-009).
"""

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from training import dataset as ds
from training.settings import TrainerSettings

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def encode(path: Path, max_side: int, quality: int = 90) -> bytes:
    """JPEG RGB sans métadonnées, côté max limité (les images d'origine font ~300 px)."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        if max(image.size) > max_side:
            image.thumbnail((max_side, max_side))
        out = BytesIO()
        image.save(out, format="JPEG", quality=quality)
        return out.getvalue()


def shuffled(files: list[Path], seed: int) -> list[Path]:
    """Ordre déterministe (graine) : les premiers sont pris, les suivants servent de réserve."""
    ordered = sorted(files)
    random.Random(seed).shuffle(ordered)
    return ordered


def select(files: list[Path], count: int, seed: int) -> list[Path]:
    return shuffled(files, seed)[:count]


def exists(client: Any, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
    except Exception:
        return False
    return True


def collect(
    client: Any, bucket: str, prefix: str, brand: str, files: list[Path], args: argparse.Namespace
) -> tuple[list[tuple[Path, bytes | None]], int]:
    """Jusqu'à `per_brand` images lisibles (données à envoyer, ou None si déjà présentes)."""
    chosen: list[tuple[Path, bytes | None]] = []
    unreadable = 0
    for path in shuffled(files, args.seed):
        if len(chosen) >= args.per_brand:
            break
        key = f"{prefix}/{brand}/{path.stem}.jpg"
        if not args.force and exists(client, bucket, key):
            chosen.append((path, None))
            continue
        try:
            chosen.append((path, encode(path, args.max_side)))
        except Exception as exc:
            unreadable += 1
            print(f"[reference] ignoré (illisible) : {brand}/{path.name} : {exc}")
    chosen.sort(key=lambda item: item[0])
    return chosen, unreadable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="dossier avec un sous-dossier par marque")
    parser.add_argument("--per-brand", type=int, default=50)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--max-side", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--prefix", default=None, help="défaut : TRAIN_REFERENCE_PREFIX (reference)"
    )
    parser.add_argument(
        "--brands", default="", help="sous-ensemble de marques, séparées par des virgules"
    )
    parser.add_argument("--force", action="store_true", help="renvoie les objets déjà présents")
    args = parser.parse_args(argv)

    settings = TrainerSettings()
    prefix = (args.prefix or settings.reference_prefix or "reference").strip("/")
    source = Path(args.source)
    if not source.is_dir():
        sys.exit(f"[reference] dossier introuvable : {source}")
    wanted = {b.strip() for b in args.brands.split(",") if b.strip()}
    brands = sorted(
        d.name for d in source.iterdir() if d.is_dir() and (not wanted or d.name in wanted)
    )
    if not brands:
        sys.exit("[reference] aucun sous-dossier de marque trouvé")

    client = ds.s3_client(settings)
    bucket = settings.s3_bucket_dataset
    lines: list[dict[str, str]] = []
    counts: dict[str, dict[str, int]] = {}
    uploaded = skipped = 0
    for brand in brands:
        files = [p for p in (source / brand).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]
        chosen, unreadable = collect(client, bucket, prefix, brand, files, args)
        n_val = max(1, round(len(chosen) * args.val_ratio)) if len(chosen) >= 2 else 0
        counts[brand] = {"train": len(chosen) - n_val, "val": n_val, "unreadable": unreadable}
        for index, (path, data) in enumerate(chosen):
            key = f"{prefix}/{brand}/{path.stem}.jpg"
            if data is not None:
                client.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg")
                uploaded += 1
            else:
                skipped += 1
            lines.append(
                {
                    "key": key,
                    "brand": brand,
                    "split": "val" if index < n_val else "train",
                    "review_id": f"ref-{brand}-{path.stem}".replace(" ", "_"),
                    "source": source.name,
                }
            )
        note = f", {unreadable} illisible(s) ignorée(s)" if unreadable else ""
        print(f"[reference] {brand:14s} {len(chosen):4d} images ({n_val} val{note})")

    manifest = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode(
        "utf-8"
    )
    client.put_object(
        Bucket=bucket,
        Key=f"{prefix}/manifest.jsonl",
        Body=manifest,
        ContentType="application/x-ndjson",
    )
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "source": source.name,
        "per_brand": args.per_brand,
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "brands": counts,
        "samples": len(lines),
    }
    client.put_object(
        Bucket=bucket,
        Key=f"{prefix}/summary.json",
        Body=json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(
        f"[reference] terminé : {len(lines)} images ({uploaded} envoyées, {skipped} déjà présentes), "
        f"{len(brands)} marques, s3://{bucket}/{prefix}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
