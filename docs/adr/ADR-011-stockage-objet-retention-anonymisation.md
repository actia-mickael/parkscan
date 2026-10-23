# ADR-011 : Stockage objet, conventions de clés, URLs présignées, rétention et anonymisation

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Les images sont des données personnelles (plaques, véhicules, parfois personnes). Elles n'ont pas
leur place en base relationnelle, doivent être servies au navigateur sans transiter par le backend,
et ne doivent pas être conservées sans limite.

## Décision

1. **Buckets** : `parkscan-captures` (`<tenant>/<site>/<aaaa>/<mm>/<jj>/<passage>/{full,plate,vehicle}.jpg`),
   `parkscan-dataset` (`labeled/<marque>/<écart>.jpg`, `versions/<version>/manifest.jsonl` et `summary.json`),
   `mlflow` (artefacts). Garage en dev/démo, S3 managé en production ; le backend seul écrit.
2. **URLs présignées** (durée courte, `PRESIGN_EXPIRES_SECONDS`), signées sur l'adresse publique
   du stockage ; le back-office les demande à l'API, qui vérifie le droit d'accès au passage.
3. **Rétention** : au-delà de `retention_days` (site > locataire > `RETENTION_DAYS`), les trois
   images sont supprimées, la plaque remplacée par un haché à clé (HMAC-SHA256 tronqué à 12
   caractères), le résultat brut du service ML effacé, les écarts en attente rejetés. Tâche
   périodique du backend, DAG Airflow `retention`, commande `make backend-retention`.
4. **Jeu d'entraînement** : la zone de la plaque est floutée au moment de la copie du crop validé.
   Les versions du jeu sont des manifestes (références), pas des copies.

## Conséquences

Les passages anonymisés restent comptés dans les statistiques et regroupables par haché ; ils ne
sont plus rattachables à une personne. La clé d'anonymisation ne doit pas changer après usage.
