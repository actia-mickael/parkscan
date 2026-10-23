# ADR-001 : Multi-locataires par schéma partagé (`tenant_id` + filtrage par dépendance)

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

ParkScan AI sert plusieurs exploitants de parkings. Chaque exploitant ne doit jamais voir les
données d'un autre ; le nombre de locataires est modeste (dizaines), les volumes par locataire aussi.

## Décision

Un seul schéma Postgres. Toutes les tables métier portent `tenant_id` (et `site_id` pour les objets
rattachés à un parking). L'utilisateur courant est résolu par une dépendance FastAPI qui porte son
locataire et ses sites autorisés ; toute requête de lecture ou d'écriture passe par un filtre commun
(`scope_filter`) et toute lecture d'un objet par identifiant vérifie son locataire (404 sinon, pas
403 : l'existence même de l'objet n'est pas révélée). Les contraintes d'unicité sont composées
avec `tenant_id` (ex. plaque normalisée par locataire).

## Alternatives écartées

Un schéma Postgres par locataire : migrations multipliées, pool de connexions par schéma, peu de
bénéfice au volume visé. Une base par locataire : idem, en pire.

## Conséquences

Un test automatisé d'isolation (locataire étranger, administrateur étranger) accompagne chaque
domaine ; le jeu de démonstration comporte deux locataires pour rendre l'isolation visible.
