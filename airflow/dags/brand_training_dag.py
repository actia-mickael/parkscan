"""DAG 1 : entraînement du classifieur de marques à partir des écarts validés par les opérateurs.

Hebdomadaire (dimanche 03:00, heure de Paris) ou manuel (`make mlops-trigger-training`). Un seul
run actif. Enchaînement : préparation suffisante ? → version du jeu (backend) → entraînement dans
l'image `trainer` (opérateur Docker) → déclaration de la version au backend → DAG de promotion.
Paramètre `force` : ignorer le seuil d'écarts nouveaux.
"""

import json

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import dag, task
from parkscan_common import backend, config


@dag(
    dag_id="brand_training",
    schedule="0 3 * * 0",
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Paris"),
    catchup=False,
    max_active_runs=1,
    tags=["parkscan", "brand", "training"],
    params={"force": False},
    doc_md=__doc__,
)
def brand_training() -> None:
    @task.short_circuit
    def check_readiness(**context) -> bool:
        readiness = backend.get("/api/v1/training/readiness")
        force = bool(context["params"].get("force"))
        print(f"[check_readiness] {readiness} force={force}")
        return force or bool(readiness["ready"])

    @task
    def build_dataset_version() -> dict:
        result = backend.post(
            "/api/v1/training/datasets", {"val_ratio": 0.2, "seed": 42, "min_per_class": 2}
        )
        print(f"[build_dataset_version] {result}")
        if result["samples"] == 0:
            raise RuntimeError("aucun échantillon étiqueté exploitable : jeu vide")
        return result

    train = DockerOperator(
        task_id="train",
        image=config.TRAINER_IMAGE,
        command=[
            "python",
            "-m",
            "training.train_brand",
            "--dataset-version",
            "{{ ti.xcom_pull(task_ids='build_dataset_version')['dataset_version'] }}",
        ],
        environment=config.trainer_environment(),
        docker_url=config.DOCKER_URL,
        network_mode=config.DOCKER_NETWORK,
        auto_remove="success",
        mount_tmp_dir=False,
        do_xcom_push=True,  # dernière ligne de la sortie : résumé JSON de l'entraînement
        doc_md="Affinage EfficientNet-B0 à partir du modèle de production, journalisé dans MLflow.",
    )

    @task
    def register_in_backend(summary_line: str) -> dict:
        summary = json.loads(summary_line)
        body = {
            "name": summary["name"],
            "version": int(summary["version"]),
            "run_id": summary["run_id"],
            "source": summary.get("source"),
            "dataset_version": summary["dataset_version"],
            "metrics": summary["metrics"],
            "baseline_metrics": summary["baseline_metrics"],
            "labels_count": summary["labels_count"],
        }
        registered = backend.post("/api/v1/models/versions", body)
        print(f"[register_in_backend] {registered}")
        return {"name": summary["name"], "version": int(summary["version"])}

    trigger_promotion = TriggerDagRunOperator(
        task_id="trigger_promotion",
        trigger_dag_id="brand_promotion",
        conf={
            "name": "{{ ti.xcom_pull(task_ids='register_in_backend')['name'] }}",
            "version": "{{ ti.xcom_pull(task_ids='register_in_backend')['version'] }}",
        },
        wait_for_completion=False,
    )

    dataset = build_dataset_version()
    check_readiness() >> dataset >> train
    register_in_backend(train.output) >> trigger_promotion


brand_training()
