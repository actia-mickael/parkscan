"""Réentraînement : préparation, version du jeu (manifeste + export), versions et promotions."""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Decision, MismatchReview, Passage, PassageStatus, ReviewStatus, Site, User
from tests.conftest import auth_headers
from tests.fakes import MemoryStorage

INTERNAL = {"X-Internal-Token": get_settings().internal_token}


async def make_review(
    session: AsyncSession, site: Site, brand: str, status: ReviewStatus = ReviewStatus.validated
) -> MismatchReview:
    passage = Passage(
        tenant_id=site.tenant_id,
        site_id=site.id,
        client_request_id=uuid.uuid4().hex,
        status=PassageStatus.ok,
        decision=Decision.allowed,
        decision_reason="whitelist_match",
    )
    session.add(passage)
    await session.flush()
    review = MismatchReview(
        tenant_id=site.tenant_id,
        site_id=site.id,
        passage_id=passage.id,
        predicted_brand="renault",
        predicted_conf=0.9,
        declared_brand=brand,
        status=status,
        final_brand=brand,
        source_crop_key=f"crops/{passage.id}.jpg",
        dataset_key=f"labeled/{brand}/{passage.id}.jpg",
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


@pytest.fixture
def small_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "min_dataset_size", 3)


async def test_readiness_requires_internal_token(client: AsyncClient, agent: User) -> None:
    assert (await client.get("/api/v1/training/readiness")).status_code == 401
    assert (
        await client.get("/api/v1/training/readiness", headers=auth_headers(agent))
    ).status_code == 401


async def test_readiness_counts_new_and_total(
    client: AsyncClient, db_session: AsyncSession, site: Site, small_threshold: None
) -> None:
    # La base de dev est partagée : on raisonne en écart par rapport à l'état initial.
    before = (await client.get("/api/v1/training/readiness", headers=INTERNAL)).json()
    await make_review(db_session, site, "dacia")
    await make_review(db_session, site, "dacia")
    await make_review(db_session, site, "kia", status=ReviewStatus.exported)
    after = (await client.get("/api/v1/training/readiness", headers=INTERNAL)).json()
    assert after["new_validated"] == before["new_validated"] + 2
    assert after["total_labeled"] == before["total_labeled"] + 3
    assert after["by_brand"]["dacia"] == before["by_brand"].get("dacia", 0) + 2
    assert after["by_brand"]["kia"] == before["by_brand"].get("kia", 0) + 1
    assert after["min_dataset_size"] == 3
    assert after["ready"] is (after["new_validated"] >= 3)


async def test_dataset_version_builds_manifest_and_exports(
    client: AsyncClient, db_session: AsyncSession, site: Site, storage: MemoryStorage
) -> None:
    mine = [await make_review(db_session, site, "dacia") for _ in range(3)]
    mine.append(await make_review(db_session, site, "saab"))
    exported = await make_review(db_session, site, "kia", status=ReviewStatus.exported)

    response = await client.post(
        "/api/v1/training/datasets",
        json={"val_ratio": 0.34, "seed": 1, "min_per_class": 1},
        headers=INTERNAL,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dropped"] == {}
    assert body["samples"] >= 5 and body["new_samples"] >= 4
    assert body["classes"]["dacia"] >= 3 and body["classes"]["saab"] >= 1
    assert body["train"] + body["val"] == body["samples"]

    bucket = get_settings().s3_bucket_dataset
    manifest = storage.objects[(bucket, body["manifest_key"])].decode()
    rows = {r["review_id"]: r for r in (json.loads(line) for line in manifest.splitlines())}
    for review in [*mine, exported]:
        assert str(review.id) in rows
        assert rows[str(review.id)]["key"] == review.dataset_key
    assert {r["split"] for r in rows.values()} == {"train", "val"}
    summary = json.loads(storage.objects[(bucket, body["summary_key"])])
    assert summary["dataset_version"] == body["dataset_version"]

    readiness = (await client.get("/api/v1/training/readiness", headers=INTERNAL)).json()
    assert readiness["new_validated"] == 0  # tout le jeu cumulé est désormais exporté
    samples = (await client.get("/api/v1/training/samples", headers=INTERNAL)).json()
    by_id = {s["id"]: s for s in samples}
    assert all(by_id[str(r.id)]["dataset_version"] == body["dataset_version"] for r in mine)
    assert (
        by_id[str(exported.id)]["dataset_version"] is None
    )  # déjà exporté : version d'origine conservée


async def test_versions_and_promotion_flow(client: AsyncClient, admin: User, agent: User) -> None:
    # Nom unique : la base de dev partagée contient de vraies versions de brand_classifier.
    name = f"test_model_{uuid.uuid4().hex[:8]}"
    create = await client.post(
        "/api/v1/models/versions",
        json={
            "name": name,
            "version": 2,
            "run_id": "abc",
            "metrics": {"accuracy": 0.9},
            "labels_count": 23,
        },
        headers=INTERNAL,
    )
    assert create.status_code == 201, create.text
    assert create.json()["status"] == "candidate"
    assert (
        await client.post("/api/v1/models/versions", json={"name": "x", "version": 1})
    ).status_code == 401

    promote = await client.post(
        "/api/v1/models/promotions",
        json={
            "name": name,
            "version": 2,
            "decision": "promoted",
            "reason": "première production",
            "candidate_metrics": {"accuracy": 0.9},
            "baseline_metrics": {"accuracy": 0.0},
        },
        headers=INTERNAL,
    )
    assert promote.status_code == 201, promote.text
    assert promote.json()["previous_version"] is None

    # Une nouvelle version promue relègue la précédente ; une version inconnue est créée à la volée
    second = await client.post(
        "/api/v1/models/promotions",
        json={
            "name": name,
            "version": 3,
            "decision": "promoted",
            "reason": "meilleure",
        },
        headers=INTERNAL,
    )
    assert second.json()["previous_version"] == 2
    rejected = await client.post(
        "/api/v1/models/promotions",
        json={
            "name": name,
            "version": 4,
            "decision": "rejected",
            "reason": "moins bonne",
        },
        headers=INTERNAL,
    )
    assert rejected.status_code == 201

    versions = (await client.get("/api/v1/models/versions", headers=auth_headers(agent))).json()
    status_by_version = {v["version"]: v["status"] for v in versions if v["name"] == name}
    assert status_by_version == {2: "previous", 3: "production", 4: "rejected"}
    promotions = [
        p
        for p in (await client.get("/api/v1/models/promotions", headers=auth_headers(admin))).json()
        if p["name"] == name
    ]
    assert [p["decision"] for p in promotions] == ["rejected", "promoted", "promoted"]
