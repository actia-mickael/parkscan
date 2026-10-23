# ADR-010 : Agent de bord minimal sans inférence locale ; idempotence ; politique hors ligne

- Statut : accepté (étape 6 à livrer)
- Date : 23 octobre 2026

## Contexte

La barrière dispose d'un petit calculateur et d'un réseau parfois instable. Embarquer les modèles
multiplierait les versions à maintenir sur le terrain.

## Décision

L'agent capture (RTSP ou fichier vidéo), déclenche sur mouvement, choisit l'image la plus nette, et
envoie au backend avec une clé API et un `client_request_id` généré avant l'envoi et conservé pour
les rejeux. Hors ligne : les captures sont mises en file locale et rejouées sans doublon ; la liste
blanche du site est mise en cache (ETag) pour une décision locale de secours selon
`EDGE_OFFLINE_POLICY` (`deny` par défaut, `open` possible par site). Aucune inférence embarquée.

## Conséquences

Le simulateur (`make edge-sim`) partage le même client que l'agent réel : les comportements
d'idempotence et de rejeu sont testés sans caméra. L'agent réel (RTSP, déclenchement, spool) est
l'étape 6 du plan.
