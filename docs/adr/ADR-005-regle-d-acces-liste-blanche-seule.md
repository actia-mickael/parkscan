# ADR-005 : Règle d'accès sur liste blanche seule ; écart de marque informatif ; seuils par site

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Le prototype refusait l'accès quand la marque reconnue différait de la marque déclarée. Le
classifieur de marques est faillible (82 % sur son jeu de validation, 22 marques) : en faire une
condition d'accès bloquerait des ayants droit.

## Décision

L'accès est accordé si et seulement si la plaque lue (confiance ≥ `ocr_threshold`) correspond à un
véhicule du site dont l'accès est activé, le résident actif, et la période de validité respectée.
Tout le reste refuse (plaque inconnue, lecture peu sûre, service ML indisponible). L'écart de
marque (confiance ≥ `brand_threshold`) est enregistré et mis en file de validation : il informe
l'opérateur et alimente le réentraînement, il ne décide jamais. Les seuils sont lus site > locataire
> défauts à chaque capture.

## Conséquences

Un véhicule usurpant une plaque passe : l'écart de marque le signale a posteriori ; une politique
plus stricte pourra être proposée par site (refus si écart confiant) sans changer l'architecture.
