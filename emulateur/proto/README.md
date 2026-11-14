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

**Pas de temps : E3 garantit 300 s** (son outil `valider` refuse tout autre pas).
**E4 tolère n'importe quel pas** : le rejeu se base sur le `t_s` réel de chaque
ligne, **aucun pas n'est codé en dur**. Les petits scénarios de test de
`scenarios_exemple/` ont volontairement un pas irrégulier (720 s, 780 s) pour le
vérifier ; ils ne passeraient pas `valider` et ne servent qu'aux tests de E4.
C'est E5 qui décide de sous-échantillonner, pas E4.

Hauteurs : en mm depuis le **zéro d'échelle de la station** (non comparables
entre stations) ; `65535` = mesure invalide.

Les scénarios réels viennent de E3, dans [`../../donnees/scenarios/`](../../donnees)
(noms `scenario_NN_<code_station>.csv`) : 5 crues réelles du même épisode
(03/11 au 09/11/2026, 1 729 points chacune, pic le 06/11), plus 2 scénarios
simulés de 24 h, dont un avec trous (`scenario_00b_SIMULE_trous.csv`). Trois petits
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
| `-b`, `--boucle` | rejouer en boucle : `t_s` et `horodatage` restent croissants d'un tour à l'autre (décalés d'une durée de scénario), car E5 calcule des écarts en `uint32` |
| `-n`, `--max` | s'arrêter après N mesures |
| `--muet` | ne pas afficher chaque mesure |

### Réglage du facteur d'accélération

Chaque point est livré à l'échéance absolue `début + t_s / facteur` : les
retards ne s'accumulent pas (un avertissement s'affiche si la machine ne suit
pas). Pour un pas nominal de 300 s :

| Facteur | Attente par point | Un scénario de 24 h dure |
|---|---|---|
| `1` | 300 s (temps réel) | 24 h |
| `60` | 5 s | ~24 min |
| `900` | 0,33 s | ~1,6 min |
| `3600` | 0,083 s | ~24 s |

Choisir le facteur selon le besoin : petit pour observer, grand pour une campagne
rapide. Il ne change **que la vitesse de rejeu**, jamais les valeurs ni l'ordre.

> **Avec la vraie radio, le facteur est plafonné par le duty cycle de 1 % (EU868).**
> Le rejeu accélère le temps du scénario, pas la radio. En SF10, une trame de
> 12 octets + 13 octets d'en-tête LoRaWAN dure ~412 ms, soit ≥ ~41 s entre deux
> trames : en mode naïf (1 trame / 300 s simulées), **facteur max ≈ ×7**
> (×10 en LoRa point à point, 289 ms). Au-delà, utiliser le temps d'air
> **calculé** par les compteurs (E6), sans radio.

## Brancher le reste du firmware

`rejouer()` est un générateur : le consommateur (E5) s'y branche directement.

```python
from rejeu import parser_csv, rejouer

mesures = parser_csv("scenarios_exemple/nominal.csv")
for m in rejouer(mesures, facteur=60):
    traiter(m)   # E5 décide d'émettre -> E1 encode -> E6 compte
```

En C++ (ESP32), même boucle : lire la série, puis pour chaque `Mesure`, dormir
jusqu'à l'échéance `début + t_s / facteur` (sommeil léger ou `deep sleep` émulé)
avant de passer la mesure à E5.

## Portage ESP32

Statut : **prototype PC validé**. Le portage C++/Arduino dépend du choix de
stockage du scénario (flash embarquée vs carte SD vs flux série depuis le PC),
à trancher par B3. La struct `Mesure` et la logique de `rejouer()` ne changent
pas avec ce choix.
