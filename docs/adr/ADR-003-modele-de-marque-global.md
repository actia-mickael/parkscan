# ADR-003 : Modèle de marque global, entraîné sur les validations de tous les locataires

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Chaque locataire valide quelques dizaines d'écarts par mois : trop peu pour entraîner un modèle
par locataire. La marque d'un véhicule n'est pas une donnée propre à un exploitant.

## Décision

Un seul classifieur de marques, enregistré sous `brand_classifier` dans MLflow, servi à tous. Le
jeu d'entraînement agrège les crops validés de tous les locataires, plaque floutée (ADR-011), sans
identifiant de locataire ni de résident. Les versions et décisions de promotion sont globales
(tables `model_versions`, `model_promotions`, sans `tenant_id`).

## Conséquences

Un locataire bénéficie des validations des autres. Les seuils de décision (`brand_threshold`,
`min_dataset_size`…) restent réglables par locataire et par site. Un modèle par locataire resterait
possible plus tard en préfixant le nom du modèle enregistré.
