"""Simulateur d'agent de bord : rejoue un dossier d'images vers l'API comme le ferait une caméra.

Usage : parkscan-edge-sim --dir /opt/demo_images [--interval 1.0] [--loop]
Variables : EDGE_API_URL, EDGE_API_KEY
"""

import argparse
import sys
import time
from pathlib import Path

from parkscan_edge.client import ApiUnreachableError, CaptureClient
from parkscan_edge.config import EdgeSettings

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="dossier d'images à rejouer")
    parser.add_argument("--interval", type=float, default=1.0, help="secondes entre deux captures")
    parser.add_argument("--loop", action="store_true", help="rejouer en boucle")
    args = parser.parse_args()

    settings = EdgeSettings()
    if not settings.api_key:
        print("EDGE_API_KEY manquant", file=sys.stderr)
        return 2
    images = sorted(p for p in Path(args.dir).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        print(f"aucune image dans {args.dir}", file=sys.stderr)
        return 1

    client = CaptureClient(settings)
    sent = 0
    try:
        while True:
            for path in images:
                try:
                    result = client.send(path.read_bytes())
                except ApiUnreachableError as exc:
                    print(f"{path.name:36s} API injoignable ({exc})", flush=True)
                    continue
                flag = " ÉCART" if result.is_mismatch else ""
                dup = " (rejeu)" if result.duplicate else ""
                print(
                    f"{path.name:36s} {result.decision:7s} {result.reason:16s} "
                    f"plaque={result.plate_norm or '-':9s} marque={result.brand or '-':12s}"
                    f"{flag}{dup}  {result.round_trip_ms} ms",
                    flush=True,
                )
                sent += 1
                time.sleep(args.interval)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
    print(f"{sent} captures envoyées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
