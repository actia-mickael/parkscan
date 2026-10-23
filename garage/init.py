"""Initialise un nœud Garage via son API d'administration : disposition, buckets, clé d'accès.

Idempotent : relançable sans effet si tout est déjà en place. Bibliothèque standard uniquement.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

ADMIN_URL = os.environ.get("GARAGE_ADMIN_URL", "http://garage:3903").rstrip("/")
TOKEN = os.environ["GARAGE_ADMIN_TOKEN"]
BUCKETS = os.environ["BUCKETS"].split()
ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
SECRET_KEY = os.environ["S3_SECRET_KEY"]
CAPACITY = int(os.environ.get("GARAGE_CAPACITY_BYTES", "20000000000"))
ZONE = os.environ.get("GARAGE_ZONE", "dev")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{ADMIN_URL}{path}",
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return error.code, {"raw": raw.decode(errors="replace")}


def wait_ready(attempts: int = 60) -> None:
    """Attend que l'API d'administration réponde. Avant la première disposition, /health renvoie 503 :
    toute réponse HTTP, quel que soit son code, signifie que le démon est joignable."""
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{ADMIN_URL}/health", timeout=3):
                return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    sys.exit("[garage-init] Garage injoignable après 60 s")


def ensure_layout() -> None:
    status_code, status = call("GET", "/v2/GetClusterStatus")
    if status_code != 200 or not isinstance(status, dict):
        sys.exit(f"[garage-init] GetClusterStatus a échoué : {status_code} {status}")
    nodes = [n for n in status["nodes"] if n.get("isUp")]
    if not nodes:
        sys.exit("[garage-init] aucun nœud connecté")
    node = nodes[0]
    if node.get("role"):
        print(f"[garage-init] disposition déjà appliquée (nœud {node['id'][:16]}…)")
        return
    code, result = call(
        "POST",
        "/v2/UpdateClusterLayout",
        {"roles": [{"id": node["id"], "zone": ZONE, "capacity": CAPACITY, "tags": ["dev"]}]},
    )
    if code != 200:
        sys.exit(f"[garage-init] UpdateClusterLayout a échoué : {code} {result}")
    version = int(status["layoutVersion"]) + 1
    code, result = call("POST", "/v2/ApplyClusterLayout", {"version": version})
    if code != 200:
        sys.exit(f"[garage-init] ApplyClusterLayout a échoué : {code} {result}")
    print(f"[garage-init] disposition v{version} appliquée ({CAPACITY / 1e9:.0f} Go, zone {ZONE})")


def ensure_bucket(alias: str) -> str:
    code, info = call("GET", f"/v2/GetBucketInfo?globalAlias={alias}")
    if code == 200 and isinstance(info, dict):
        return info["id"]
    code, info = call("POST", "/v2/CreateBucket", {"globalAlias": alias})
    if code != 200 or not isinstance(info, dict):
        sys.exit(f"[garage-init] CreateBucket {alias} a échoué : {code} {info}")
    print(f"[garage-init] bucket créé : {alias}")
    return info["id"]


def ensure_key() -> None:
    code, _ = call("GET", f"/v2/GetKeyInfo?id={ACCESS_KEY}")
    if code == 200:
        return
    code, info = call(
        "POST",
        "/v2/ImportKey",
        {"accessKeyId": ACCESS_KEY, "secretAccessKey": SECRET_KEY, "name": "parkscan"},
    )
    if code != 200:
        sys.exit(f"[garage-init] ImportKey a échoué : {code} {info}")
    print(f"[garage-init] clé d'accès importée : {ACCESS_KEY}")


def allow(bucket_id: str, alias: str) -> None:
    code, info = call(
        "POST",
        "/v2/AllowBucketKey",
        {
            "bucketId": bucket_id,
            "accessKeyId": ACCESS_KEY,
            "permissions": {"read": True, "write": True, "owner": True},
        },
    )
    if code != 200:
        sys.exit(f"[garage-init] AllowBucketKey {alias} a échoué : {code} {info}")


def main() -> None:
    wait_ready()
    ensure_layout()
    ensure_key()
    for alias in BUCKETS:
        allow(ensure_bucket(alias), alias)
    print(f"[garage-init] prêt : buckets {', '.join(BUCKETS)}")


if __name__ == "__main__":
    main()
