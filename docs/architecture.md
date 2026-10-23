# Architecture de ParkScan AI

ParkScan AI est un SaaS multi-locataires de contrôle d'accès aux parkings par lecture de plaque,
avec vérification de la marque du véhicule et réentraînement continu à partir des validations des
opérateurs. Un locataire (exploitant) possède des sites (parkings), chacun équipé d'un agent de
bord (caméra) identifié par une clé API.

## Services (Docker Compose, réseau `parkscan_net`)

| Service | Rôle | Profil |
|---|---|---|
| `db` (Postgres 16) | données métier : locataires, sites, utilisateurs, résidents, véhicules, passages, écarts, versions de modèles | core |
| `backend` (FastAPI async) | API métier `/api/v1`, décision d'accès, ingestion, file des écarts, rétention | core |
| `ml` (FastAPI + torch CPU) | inférence : détection de plaque, OCR, détection de véhicule, classification de marque | core |
| `frontend` (React, Vite, nginx en prod) | back-office opérateur | core |
| `garage` + `garage-init` | stockage objets S3 compatible (captures, jeu de données, artefacts MLflow) | core |
| `mlflow` + `mlflow-db` | registre de modèles (alias `production`), suivi des entraînements, artefacts proxifiés | mlops |
| `airflow-*` + `airflow-db` | orchestration : entraînement, promotion, rétention | mlops |
| `trainer` (image) | entraînement du classifieur, lancé par Airflow via l'opérateur Docker | tools |
| `edge-sim` | simulateur d'agent de bord (rejoue des images vers l'API) | sim |

## Flux principaux

1. **Passage** : l'agent de bord envoie une image (`POST /ingest/capture`, clé API, identifiant de
   requête idempotent). Le backend appelle le service ML (`POST /infer`), applique la règle d'accès
   (liste blanche du site, validité, accès activé), enregistre un passage unique, envoie l'image et
   les crops au stockage, et crée un écart si la marque reconnue diffère de la marque déclarée.
2. **Validation** : un opérateur valide ou rejette l'écart dans le back-office ; la marque confirmée
   met à jour le véhicule et le crop (plaque floutée) rejoint le jeu étiqueté `labeled/<marque>/`.
3. **Réentraînement** (hebdomadaire ou manuel) : le DAG `brand_training` fige une version du jeu
   (manifeste cumulatif), affine le classifieur dans l'image `trainer`, journalise dans MLflow et
   déclenche `brand_promotion`, qui compare le candidat à la production sur le même jeu de
   validation, déplace l'alias et recharge le service ML à chaud.
4. **Rétention** : au-delà de la durée de conservation, images supprimées et plaques hachées.

## Données et isolation

Toutes les tables métier portent `tenant_id` ; chaque requête est filtrée par le locataire de
l'utilisateur et, pour les gestionnaires et agents, par leurs sites. Le modèle de marque est global
(ADR-003) : seules les images validées, floutées, alimentent l'entraînement. Clés de stockage :
`<tenant>/<site>/<aaaa>/<mm>/<jj>/<passage>/{full,plate,vehicle}.jpg`.

## Ports (développement)

Backend 8001 · Service ML 8002 · Back-office 5173 · Garage 3900 · MLflow 5000 · Airflow 8080 ·
Postgres 5433 (hôte).
