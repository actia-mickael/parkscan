# ADR-009 : Promotion par comparaison stricte sur un jeu de validation commun, décisions persistées

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Un candidat issu du réentraînement ne doit remplacer la production que s'il n'est pas moins bon.
Comparer des métriques calculées sur des jeux différents (celles du run de production, celles du
candidat) ne prouve rien : le jeu change à chaque version.

## Décision

1. **Le même jeu de validation pour les deux.** L'entraînement évalue le candidat ET le modèle de
   production courant sur la partition `val` de la version du jeu, et journalise les deux séries
   (`accuracy`, `top3_accuracy`, `f1_macro` et leurs `baseline_*`). Les marques que la production
   ignore comptent comme des erreurs pour elle.
2. **Règle stricte** : promotion si et seulement si les trois métriques du candidat sont
   supérieures ou égales à celles de la référence. Promotion d'office s'il n'y a pas de production.
   Métriques incomplètes : rejet par prudence.
3. **Promotion = alias.** `production` passe sur le candidat, l'ancienne version reçoit `previous`
   (retour arrière : inverser les alias puis recharger). Tag `candidate_status` : `PROMOTED` ou
   `REJECTED`. Le service ML est rechargé à chaud juste après (`POST /models/reload`).
4. **Décisions persistées côté backend** (`model_versions`, `model_promotions`) : version, raison
   lisible, métriques comparées, version précédente. Le back-office les affiche (page « Modèles »).

## Conséquences

- Un candidat meilleur sur une métrique mais moins bon sur une autre est rejeté : choix assumé,
  la régression silencieuse coûte plus cher qu'un réentraînement différé.
- Un jeu de validation très petit (démo) rend la règle peu discriminante ; en production, le seuil
  `MIN_DATASET_SIZE` garantit un jeu significatif.
