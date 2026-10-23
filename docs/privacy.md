# Données personnelles dans ParkScan AI

## Inventaire

| Donnée | Où | Finalité | Durée |
|---|---|---|---|
| Résidents (identité, contact, adresse) | table `residents` | gestion des ayants droit | durée du contrat, suppression par l'exploitant |
| Véhicules (plaque, marque, modèle) | table `vehicles` | liste blanche d'accès | idem |
| Passages (plaque lue, décision, horodatage, images) | table `passages`, stockage `parkscan-captures` | contrôle d'accès, traçabilité, amélioration du modèle | `RETENTION_DAYS` (30 jours par défaut), réglable par locataire et par site |
| Écarts de marque (crop véhicule) | table `mismatch_reviews`, stockage `parkscan-dataset` | réentraînement | crop **plaque floutée**, conservé tant qu'il sert à l'entraînement |
| Utilisateurs du back-office | table `users` | authentification, rôles | durée du compte |
| Journaux applicatifs | sortie des conteneurs | exploitation | rotation du moteur de conteneurs |

Les images de démonstration du dépôt portent des plaques fictives.

## Rétention et anonymisation (ADR-011)

Au-delà de la durée de conservation effective (site > locataire > `RETENTION_DAYS`) :

- les trois images du passage (vue complète, plaque, véhicule) sont supprimées du stockage ;
- la plaque est remplacée par un haché à clé (HMAC-SHA256 tronqué, clé `ANONYMIZATION_SECRET`) :
  les statistiques restent possibles (regroupements), l'identification ne l'est plus ;
- le résultat brut du service ML (qui contenait le texte lu) est effacé ;
- un écart encore en attente sur ce passage est rejeté.

Le traitement tourne dans le backend (périodique), est traçable via le DAG Airflow `retention`,
et peut être lancé ou simulé à la main (`make backend-retention DRY=1`).

## Jeu d'entraînement

Seuls les crops de véhicules validés par un opérateur entrent dans le jeu étiqueté, après floutage de
la zone de la plaque. Le modèle de marque est global (partagé entre locataires) mais n'apprend que
des formes de véhicules, jamais une plaque ni une identité.

## Droits des personnes

L'exploitant (locataire) est responsable de traitement ; ParkScan AI est l'outil. Pour une demande
d'accès ou d'effacement : rechercher la plaque dans « Passages » (tant qu'elle n'est pas anonymisée),
supprimer le véhicule ou le résident dans le back-office (les passages liés perdent la référence au
véhicule), et lancer la rétention pour les images. Les passages déjà anonymisés ne sont plus
rattachables à une personne.

## Sécurité

Jetons d'accès courts (15 min) et de rafraîchissement révocables ; mots de passe hachés (argon2) ;
clés API hachées (secret affiché une seule fois) ; URLs d'images présignées à durée courte ; secrets
par défaut refusés en production ; isolation stricte par locataire dans chaque requête.
