# ADR-006 : Un passage = une ligne ; captures sans plaque intégrées via `status`

- Statut : accepté
- Date : 23 octobre 2026

## Contexte

Chaque capture doit laisser exactement une trace, qu'elle aboutisse à une lecture ou non, et l'agent
de bord peut rejouer un envoi (réseau coupé).

## Décision

Table `passages` unique : décision (`allowed`/`denied`), motif, et `status` (`ok`, `no_plate`,
`low_ocr_conf`, `ml_error`) qui qualifie la qualité de la capture. Idempotence par
`(site_id, client_request_id)` : un rejeu renvoie le passage existant (`duplicate: true`). Les
images (vue complète, plaque, véhicule) sont envoyées au stockage après la réponse, chacune
indépendamment ; leur absence n'invalide pas le passage.

## Conséquences

Le tableau de bord compte les captures en échec sans table séparée ; la rétention traite toutes les
lignes de la même façon ; l'écart de marque est une table à part (un passage au plus un écart).
