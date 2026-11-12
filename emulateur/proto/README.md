# E4 — Rejeu des séries (prototype PC)

Premier maillon de la boucle firmware de l'émulateur :

```
lire une mesure (E4) -> décider d'émettre (E5) -> encoder (E1) -> émettre + compter (E6) -> dormir
```

Ce dossier contient le **prototype PC en Python** de E4 : il lit un scénario CSV
de hauteur d'eau et le rejoue à une **horloge accélérée réglable**, en produisant
des objets `Mesure` que le reste du firmware consomme. Il sert à valider la
logique sans matériel, et à alimenter les tests des modes d'émission (E5) et du
moteur d'alerte (AL7).

> La logique est volontairement isolée dans `rejouer()` (un générateur) pour être
> rejouable telle quelle lors du portage C++/Arduino sur ESP32.

## Format d'entrée (fourni, figé)

Un CSV par scénario, **séparateur `;`**, une ligne d'en-tête :

| Colonne | Type | Description |
|---|---|---|
| `t_s` | entier | temps écoulé depuis le début du scénario, en secondes (commence à 0) |
| `date_utc` | ISO 8601 UTC | horodatage `AAAA-MM-JJTHH:MM:SSZ` |
| `hauteur_mm` | entier | hauteur d'eau en mm ; `65535` (`0xFFFF`) = mesure invalide |

Exemple :

```
t_s;date_utc;hauteur_mm
0;2026-10-15T00:00:00Z;1180
300;2026-10-15T00:05:00Z;1182
```

Pas de temps nominal : 5 min (300 s), **mais il peut varier**. Le rejeu se base
sur le `t_s` réel de chaque ligne : **aucun pas n'est codé en dur**. C'est E5 qui
décidera de sous-échantillonner, pas E4.

Les scénarios réels (nominal, montée rapide, crue extrême, panne réseau)
viennent de E3, dans [`../../donnees/scenarios/`](../../donnees). Deux petits
scénarios de test sont fournis ici dans `scenarios_exemple/`.

## La structure `Mesure`

Partagée avec les modes d'émission (E5) et l'encodeur (E1). Figée dans l'ossature
commune : [`emulateur/include/mesure.h`](../include/mesure.h) (version firmware
C++). La classe Python de `rejeu.py` en est le miroir.

| Champ | Firmware (C++) | Python | Sens |
|---|---|---|---|
| `t_s` | `uint32_t` | `int` | temps depuis le début du scénario (s) |
| `horodatage` | `uint32_t` (epoch UTC) | `datetime` (+ `.epoch`) | date de la mesure |
| `hauteur_mm` | `uint16_t` | `int` | hauteur en mm ; `MESURE_INVALIDE` (0xFFFF) sinon |

`m.valide` (Python) / `m.valide()` (C++) : vrai si la hauteur est exploitable.

## Usage

```bash
cd emulateur/proto

# Temps réel (1 point toutes les 5 min)
python3 rejeu.py scenarios_exemple/nominal.csv -f 1

# Accéléré x900 : 5 min -> 0,33 s
python3 rejeu.py scenarios_exemple/nominal.csv -f 900

# Montée rapide, en boucle, 20 premières mesures
python3 rejeu.py scenarios_exemple/montee_rapide.csv -f 600 -b -n 20
```

| Option | Rôle |
|---|---|
| `-f`, `--facteur` | **facteur d'accélération** > 0. `1` = temps réel ; `60` = 60x plus rapide. Défaut : `60`. |
| `-b`, `--boucle` | rejouer en boucle (1er point de chaque cycle émis sans attente) |
| `-n`, `--max` | s'arrêter après N mesures |
| `--muet` | ne pas afficher chaque mesure |

### Réglage du facteur d'accélération

L'attente réelle entre deux points vaut `(t_s[i+1] - t_s[i]) / facteur`. Pour un
pas nominal de 300 s :

| Facteur | Attente par point | Un scénario de 24 h dure |
|---|---|---|
| `1` | 300 s (temps réel) | 24 h |
| `60` | 5 s | ~24 min |
| `900` | 0,33 s | ~1,6 min |
| `3600` | 0,083 s | ~24 s |

Choisir le facteur selon le besoin : petit pour observer, grand pour une campagne
rapide. Il ne change **que la vitesse de rejeu**, jamais les valeurs ni l'ordre.

## Brancher le reste du firmware

`rejouer()` est un générateur : le consommateur (E5) s'y branche directement.

```python
from rejeu import parser_csv, rejouer

mesures = parser_csv("scenarios_exemple/nominal.csv")
for m in rejouer(mesures, facteur=60):
    traiter(m)   # E5 décide d'émettre -> E1 encode -> E6 compte
```

En C++ (ESP32), même boucle : lire la série, puis pour chaque `Mesure`, attendre
`(t_s[i+1]-t_s[i]) / facteur` (en sommeil léger ou `deep sleep` émulé) avant de
passer la mesure à E5.

## Portage ESP32

Statut : **prototype PC validé**. Le portage C++/Arduino dépend du choix de
stockage du scénario (flash embarquée vs carte SD vs flux série depuis le PC),
à trancher par B3. La struct `Mesure` et la logique de `rejouer()` ne changent
pas avec ce choix.
