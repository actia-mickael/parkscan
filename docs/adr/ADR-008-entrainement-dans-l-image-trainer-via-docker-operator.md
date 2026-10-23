# ADR-008 : Entraînement dans l'image `trainer`, orchestré par Airflow via l'opérateur Docker

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Le réentraînement du classifieur de marques doit utiliser exactement les mêmes versions de torch et
torchvision que le service d'inférence, sinon un checkpoint produit peut ne pas se charger. Airflow,
lui, doit rester léger (pas de torch, démarrage rapide, image officielle).

## Décision

1. **Cible `trainer` de `ml/Dockerfile`** : même base et même fichier de verrouillage que le service
   d'inférence, plus `boto3` (lecture du jeu de données sur le S3). La compatibilité checkpoint ↔
   chargeur est garantie par construction. L'image est construite par compose (service `trainer`,
   profil `tools`) sous le nom `parkscan-trainer:dev`.
2. **Airflow 3 sur l'image officielle** (`apache/airflow:3.3.2-python3.12`) avec le seul provider
   Docker en plus. Composants : serveur API, ordonnanceur (exécuteur local), dag-processor, base
   Postgres dédiée. Gestionnaire d'authentification simple, mot de passe administrateur fixé à
   l'initialisation.
3. **Opérateur Docker** : l'ordonnanceur monte le socket Docker (groupe `DOCKER_GID`, détecté par le
   Makefile) et lance l'image `trainer` sur le réseau `parkscan_net`, avec les variables S3 et
   MLflow. Le conteneur est supprimé en cas de succès, conservé en cas d'échec pour inspection.
   La dernière ligne de sa sortie est un résumé JSON, transmis par XCom à la tâche suivante.
4. **MLflow par API REST** depuis Airflow (recherche des versions, alias, tags, métriques d'un run) :
   pas de client Python MLflow dans l'image Airflow, donc aucun conflit de dépendances.
5. **Le backend fige le jeu de données** (`POST /training/datasets`) : manifeste cumulatif
   (train/val stratifié, graine fixe) et résumé écrits sur le S3, écarts marqués « exportés ».
   Airflow orchestre, il ne manipule pas les données.

## Conséquences

- Repli prévu si le socket Docker n'est pas accessible (hôte verrouillé) : torch CPU dans l'image
  Airflow et opérateur Bash ; non retenu par défaut à cause du poids de l'image.
- Le jeu d'entraînement est cumulatif : chaque version reprend tous les écarts validés ; « prêt »
  signifie qu'assez d'écarts nouveaux se sont accumulés (`MIN_DATASET_SIZE`).
- Une marque inconnue du modèle n'est ajoutée qu'avec au moins `TRAIN_MIN_PER_CLASS` images.
