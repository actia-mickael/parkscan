"""DAG 2 : promotion ou rejet d'un candidat du classifieur de marques.

Déclenché par le DAG d'entraînement (conf : name, version) ou manuellement (dernier candidat
« READY_FOR_PROMOTION »). Règle : le candidat est promu si, sur le même jeu de validation, son
exactitude, son top 3 et son F1 macro sont tous supérieurs ou égaux à ceux du modèle de production
(mesurés par l'entraînement : métriques `baseline_*`). Promotion d'office s'il n'y a pas de production.
Promu : alias `production` (l'ancienne version reçoit `previous`), tag PROMOTED, décision persistée
au backend, rechargement à chaud du service ML. Rejeté : tag REJECTED, décision persistée.
"""

import pendulum
from airflow.sdk import dag, task
from parkscan_common import backend, config, ml_service, mlflow_api

COMPARED = ("accuracy", "top3_accuracy", "f1_macro")


@dag(
    dag_id="brand_promotion",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Paris"),
    catchup=False,
    max_active_runs=1,
    tags=["parkscan", "brand", "promotion"],
    params={"name": config.BRAND_MODEL, "version": ""},
    doc_md=__doc__,
)
def brand_promotion() -> None:
    @task
    def load_candidate(**context) -> dict:
        params = context["params"]
        name = params.get("name") or config.BRAND_MODEL
        wanted = str(params.get("version") or "").strip()
        ready = [
            mv
            for mv in mlflow_api.search_versions(name)
            if mv["tags_dict"].get("candidate_status") == "READY_FOR_PROMOTION"
            and (not wanted or mv["version"] == wanted)
        ]
        if not ready:
            raise RuntimeError(
                f"aucun candidat READY_FOR_PROMOTION pour {name} (version demandée : {wanted or 'dernière'})"
            )
        candidate = ready[0]
        metrics = mlflow_api.run_metrics(candidate["run_id"]) if candidate.get("run_id") else {}
        result = {
            "name": name,
            "version": candidate["version_int"],
            "run_id": candidate.get("run_id"),
            "dataset_version": candidate["tags_dict"].get("dataset_version"),
            "metrics": {k: metrics.get(k) for k in (*COMPARED, "loss")},
            "baseline_metrics": {k: metrics.get(f"baseline_{k}") for k in COMPARED},
        }
        print(f"[load_candidate] {result}")
        return result

    @task
    def load_production(candidate: dict) -> dict | None:
        current = mlflow_api.version_by_alias(candidate["name"], config.PRODUCTION_ALIAS)
        if current is None:
            print("[load_production] aucune version en production")
            return None
        result = {"version": current["version_int"], "run_id": current.get("run_id")}
        print(f"[load_production] {result}")
        return result

    @task.branch
    def compare(candidate: dict, production: dict | None, **context) -> str:
        metrics, baseline = candidate["metrics"], candidate["baseline_metrics"]
        if production is None:
            reason = "aucune version en production : promotion d'office"
            promote_it = True
        elif any(metrics.get(k) is None or baseline.get(k) is None for k in COMPARED):
            reason = "métriques de comparaison incomplètes : rejet par prudence"
            promote_it = False
        else:
            checks = [(k, float(metrics[k]), float(baseline[k])) for k in COMPARED]
            promote_it = all(c >= b for _, c, b in checks)
            reason = " ; ".join(
                f"{k} {c:.3f} {'≥' if c >= b else '<'} {b:.3f}" for k, c, b in checks
            )
        context["ti"].xcom_push(key="reason", value=reason)
        print(f"[compare] promote={promote_it} : {reason}")
        return "promote" if promote_it else "reject"

    @task
    def promote(candidate: dict, production: dict | None, **context) -> dict:
        name, version = candidate["name"], candidate["version"]
        reason = context["ti"].xcom_pull(task_ids="compare", key="reason")
        if production is not None and production["version"] != version:
            mlflow_api.set_alias(name, config.PREVIOUS_ALIAS, production["version"])
        mlflow_api.set_alias(name, config.PRODUCTION_ALIAS, version)
        mlflow_api.set_version_tag(name, version, "candidate_status", "PROMOTED")
        mlflow_api.set_version_tag(name, version, "promoted_at", pendulum.now("UTC").isoformat())
        decision = backend.post(
            "/api/v1/models/promotions",
            {
                "name": name,
                "version": version,
                "decision": "promoted",
                "reason": reason,
                "candidate_metrics": _clean(candidate["metrics"]),
                "baseline_metrics": _clean(candidate["baseline_metrics"]),
                "decided_by": "airflow:brand_promotion",
            },
        )
        reloaded = ml_service.reload_models()
        served = reloaded.get("models", {}).get(name, {})
        print(f"[promote] {name} v{version} en production ; service ML sert : {served}")
        return {"decision": decision, "served": served}

    @task
    def reject(candidate: dict, **context) -> dict:
        name, version = candidate["name"], candidate["version"]
        reason = context["ti"].xcom_pull(task_ids="compare", key="reason")
        mlflow_api.set_version_tag(name, version, "candidate_status", "REJECTED")
        decision = backend.post(
            "/api/v1/models/promotions",
            {
                "name": name,
                "version": version,
                "decision": "rejected",
                "reason": reason,
                "candidate_metrics": _clean(candidate["metrics"]),
                "baseline_metrics": _clean(candidate["baseline_metrics"]),
                "decided_by": "airflow:brand_promotion",
            },
        )
        print(f"[reject] {name} v{version} rejeté : {reason}")
        return {"decision": decision}

    @task(trigger_rule="none_failed_min_one_success")
    def summary(candidate: dict, **context) -> None:
        reason = context["ti"].xcom_pull(task_ids="compare", key="reason")
        print(f"===== PROMOTION {candidate['name']} v{candidate['version']} : {reason} =====")

    candidate = load_candidate()
    production = load_production(candidate)
    decision = compare(candidate, production)
    promoted = promote(candidate, production)
    rejected = reject(candidate)
    decision >> [promoted, rejected]
    [promoted, rejected] >> summary(candidate)


def _clean(metrics: dict) -> dict:
    return {k: float(v) for k, v in metrics.items() if v is not None}


brand_promotion()
