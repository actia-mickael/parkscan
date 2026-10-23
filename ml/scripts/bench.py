"""Banc de latence : envoie des images à /infer et affiche p50 / p95 par étape.

Usage : python scripts/bench.py [--url http://localhost:8002] [--n 20] [images ou dossiers...]
"""

import argparse
import statistics
import sys
from pathlib import Path

import httpx


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += sorted(x for x in p.iterdir() if x.suffix.lower() in {".jpg", ".jpeg", ".png"})
        elif p.is_file():
            files.append(p)
    return files


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8002")
    parser.add_argument("--n", type=int, default=20, help="nombre total d'appels")
    parser.add_argument("paths", nargs="*", default=["/opt/demo_images"])
    args = parser.parse_args()

    images = collect(args.paths)
    if not images:
        print("aucune image trouvée", file=sys.stderr)
        return 1

    wall: list[float] = []
    stages: dict[str, list[float]] = {}
    with httpx.Client(base_url=args.url, timeout=30) as client:
        for i in range(args.n):
            path = images[i % len(images)]
            response = client.post("/infer", files={"image": (path.name, path.read_bytes())})
            response.raise_for_status()
            body = response.json()
            wall.append(response.elapsed.total_seconds() * 1000)
            for stage, ms in body["timings_ms"].items():
                stages.setdefault(stage, []).append(ms)
            plates = ",".join(p["text_norm"] for p in body["plates"]) or "-"
            brand = body["brand"]["label"] if body["brand"] else "-"
            print(
                f"{path.name:30s} {body['timings_ms']['total']:7.1f} ms  plaque={plates} marque={brand}"
            )

    print("\nétape          p50 (ms)   p95 (ms)")
    for stage, values in stages.items():
        print(f"{stage:12s} {statistics.median(values):9.1f} {percentile(values, 95):10.1f}")
    print(f"{'http total':12s} {statistics.median(wall):9.1f} {percentile(wall, 95):10.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
