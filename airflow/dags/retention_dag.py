"""DAG 3 : rétention quotidienne (04:30, heure de Paris).

Demande au backend de purger les images et d'anonymiser les plaques des passages plus vieux que la
durée de conservation effective (ADR-011). Le backend possède aussi sa propre tâche périodique :
ce DAG rend l'opération visible et traçable dans Airflow quand le profil mlops est actif.
"""

import pendulum
from airflow.sdk import dag, task
from parkscan_common import backend


@dag(
    dag_id="retention",
    schedule="30 4 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Paris"),
    catchup=False,
    max_active_runs=1,
    tags=["parkscan", "retention", "privacy"],
    params={"dry_run": False},
    doc_md=__doc__,
)
def retention() -> None:
    @task
    def run_retention(**context) -> dict:
        dry_run = bool(context["params"].get("dry_run"))
        report = backend.post(f"/api/v1/retention/run?dry_run={'true' if dry_run else 'false'}")
        print(f"[retention] {report}")
        return report

    run_retention()


retention()
