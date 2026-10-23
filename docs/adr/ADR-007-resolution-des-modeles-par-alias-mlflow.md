# ADR-007 : Résolution des modèles par alias MLflow « production », repli local, poids hors git

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Le service d'inférence charge deux modèles propres au produit (détecteur de plaques affiné, classifieur
de marques) et deux modèles génériques (détecteur de véhicules YOLO, OCR). Le réentraînement du
classifieur de marques est une fonctionnalité vendue : une nouvelle version doit pouvoir être promue,
servie sans redémarrage, et annulée. Les poids pèsent de 6 à 49 Mo et n'ont rien à faire dans git.

Le prototype d'origine reposait sur les « stages » MLflow (Staging/Production), dépréciés, et sur un
chargement implicite depuis le répertoire courant.

## Décision

1. **Registre MLflow, alias plutôt que stages.** Deux modèles enregistrés, `brand_classifier` et
   `plate_detector`. La version servie est celle que pointe l'alias `production` ; la promotion
   déplace l'alias (l'ancienne version reçoit `previous`). Aucun stage.
2. **Résolution au démarrage et au rechargement** (`ml/parkscan_ml/registry.py`), pilotée par
   `ML_MODEL_SOURCE` : `auto` (défaut) tente MLflow puis se replie sur `ML_WEIGHTS_DIR` ; `mlflow`
   l'exige ; `local` l'ignore. L'échec de MLflow est rapide (délai 10 s, un seul essai) pour que le
   repli ne retarde pas le démarrage. Le rechargement (`POST /models/reload`) est atomique : l'ancien
   pipeline reste servi jusqu'au succès du nouveau.
3. **Cache par version.** Les artefacts sont téléchargés dans `ML_MLFLOW_CACHE_DIR/<modèle>/v<n>` et
   marqués complets ; une version déjà présente n'est jamais retéléchargée.
4. **Contrat d'artefacts.** `model/checkpoint.pth` (+ `model/labels.json`) pour le classifieur,
   `model/plate_detector.pt` pour le détecteur. Le service cherche ces fichiers sous le dossier de la
   version, quel que soit le chemin exact renvoyé par MLflow.
5. **Artefacts proxifiés par le serveur MLflow** (`--artifacts-destination s3://mlflow/`) : seul le
   serveur détient les clés du S3 compatible (Garage en dev, S3 managé en production). Les clients
   (service ML, Airflow) ne connaissent que l'URL de suivi.
6. **Poids initiaux hors git.** Les poids produit sont publiés en Release GitHub (`weights-v1`) ;
   `make ml-fetch-weights` les place dans `ml/weights/` ; `make mlops-seed-models` les enregistre
   dans MLflow (version taguée par sha256, idempotent) et pose l'alias.
7. **Modèles génériques dans l'image.** Détecteur de véhicules et OCR sont téléchargés au build
   (`prefetch`), jamais à l'exécution ni depuis MLflow.

## Conséquences

- Le service ML fonctionne sans MLflow (profil `core` seul) et bascule sur le registre dès que le
  profil `mlops` tourne et que les poids ont été enregistrés : `make mlops-up mlops-seed-models`.
- Les versions servies sont visibles dans `GET /models` (service ML et backend) et sur la page
  « Modèles » du back-office, avec la provenance (`local` ou `mlflow`), l'alias, le numéro de version
  et le run d'origine.
- La promotion (étape 8, DAG Airflow) se réduit à déplacer un alias puis appeler le rechargement.
- Le cache local peut diverger du registre si l'on modifie une version en place dans MLflow : les
  versions sont considérées immuables, toute correction passe par une nouvelle version.
