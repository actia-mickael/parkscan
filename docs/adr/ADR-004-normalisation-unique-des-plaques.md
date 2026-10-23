# ADR-004 : Normalisation unique des plaques, unicité `(tenant_id, plate_norm)`

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Une même plaque arrive sous plusieurs formes : « AB-123-CD », « ab 123 cd », « AB123CD » (OCR).
La comparaison liste blanche ↔ lecture doit être insensible à la forme.

## Décision

Une seule fonction de normalisation (`app/core/plates.py`) : majuscules, suppression de tout ce qui
n'est pas alphanumérique. Elle s'applique à la saisie des véhicules (`plate_raw` conservée pour
l'affichage, `plate_norm` pour la recherche), au texte lu par l'OCR et aux filtres de recherche.
Unicité `(tenant_id, plate_norm)` sur les véhicules : un doublon dans le même locataire est refusé
(409), la même plaque peut exister chez deux locataires.

## Conséquences

Les caractères ambigus (O/0, I/1) ne sont pas corrigés : c'est le rôle de l'OCR et de sa confiance
(`ocr_threshold`). Les plaques étrangères sont acceptées telles quelles (longueur ≤ 12 après
normalisation).
