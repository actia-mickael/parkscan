# ADR-002 : Backend léger + service ML séparé, HTTP synchrone, pas de file en v1

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

L'inférence (torch, ultralytics, OCR) pèse 1,5 Go d'image et plusieurs secondes de chargement ; le
backend métier doit rester petit, rapide à démarrer, testable sans torch. La décision d'accès doit
être rendue en moins d'une seconde à la barrière.

## Décision

Deux services : `backend` (FastAPI async, base, stockage, règles) et `ml` (FastAPI, modèles
chargés en mémoire). Le backend appelle `POST /infer` en HTTP synchrone avec un délai borné
(`ML_TIMEOUT_MS`, 1 500 ms) ; en cas d'échec, le passage est enregistré en `ml_error` et l'accès
refusé (politique « fermé par défaut », ADR-005). Pas de file de messages en v1 : la latence
bout en bout mesurée (250 à 600 ms) tient dans le budget, et une file ajouterait un service et une
sémantique asynchrone inutile à ce stade.

## Conséquences

Le service ML est remplaçable (GPU, autre runtime) sans toucher au backend ; les tests backend
utilisent une doublure du client ML. Une file (ou plusieurs réplicas ML) sera envisagée si le
débit par barrière dépasse ce que deux workers CPU absorbent.
