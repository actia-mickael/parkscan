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

5. **Jeu de référence multi-marques.** Les seuls écarts validés sont rares et déséquilibrés (une
   marque peut dominer) ; entraîner et juger dessus seuls fait oublier les autres marques au modèle
   et rend la règle aveugle. Un jeu de référence (par défaut 50 photos par marque, issues d'un jeu
   public de reconnaissance de marques et modèles, ré-encodées sans métadonnées, découpage train/val
   figé) est importé dans le stockage (`reference/`) et fusionné à chaque entraînement avec les
   écarts validés. Les métriques de promotion portent sur l'union des deux validations ; l'exactitude
   sur les seuls écarts validés est journalisée à titre d'information (`labeled_accuracy`).

## Conséquences

- Un candidat meilleur sur une métrique mais moins bon sur une autre est rejeté : choix assumé,
  la régression silencieuse coûte plus cher qu'un réentraînement différé.
- Sans jeu de référence, un jeu de validation très petit (démo) rend la règle peu discriminante ;
  avec lui, la validation couvre toutes les marques même quand les écarts validés n'en couvrent qu'une.
- Les photos de référence ont pu servir à l'entraînement initial du modèle : la référence y est
  favorisée, le candidat aussi ; la comparaison reste équitable car les deux sont jugés sur le même jeu.
