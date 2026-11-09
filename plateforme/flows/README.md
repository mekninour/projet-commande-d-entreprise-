# Flux Node-RED

**Binôme :** B1 – Nour Mekni

| Fichier | Tâche | Rôle |
|---|---|---|
| `s2_reception.json` | S2 | Reçoit les trames brutes, les décode, contrôle `seq` et publie des mesures propres |

## S2 – Réception des trames

```
pce92/uplink ──► 1. Décoder (codec S1) ──► 2. Contrôler seq ──► pce92/mesures/<node_id>
 (trame brute)          │ rejet                   │ doublon, pertes
                        └─────────────┬───────────┘
                                      ▼
                               pce92/evenements
```

**Entrée** : le topic `pce92/uplink`, publié par le récepteur LoRa (ou par l'injecteur S5) :
`{ "received_at", "payload_hex", "rssi", "snr", "source" }`.

**Étape 1 – Décoder.** La trame est décodée avec `trame/decodeur/codec.js`, le même code que celui des tests S1. On obtient une **mesure normalisée** :

| Champ | Contenu |
|---|---|
| `node_id` | le site |
| `received_at` | l'heure de réception = l'horodatage de la mesure (règle 4 du contrat) |
| `water_mm` | le niveau en mm ; `null` si la mesure est invalide (0xFFFF) |
| `water_valid` | `false` si la mesure est invalide |
| `batt_v` | la tension en V ; `null` si inconnue |
| `seq`, `alert`, `next_min` | lus dans la trame |
| `expected_next_at` | l'heure attendue de la prochaine trame (`received_at` + `next_min`) : sert à repérer un capteur muet |
| `rssi`, `snr`, `source`, `payload_hex` | la qualité du signal, l'origine et la trame d'origine |
| `seq_gap`, `lost_before` | ajoutés à l'étape 2 : l'écart de seq et le nombre de trames perdues juste avant |

Une trame illisible (pas de `payload_hex`, mauvaise longueur, `node_id` = 0) est **rejetée** et publiée sur `pce92/evenements`.

**Étape 2 – Contrôler seq** (règle 5 du contrat), pour chaque nœud. L'écart vaut (seq − seq précédent) modulo 65536 :
- **1** : trame normale ;
- **plus de 1** : des trames ont été perdues. La mesure est gardée, et un événement `trames_perdues` est publié ;
- **0** : c'est un **doublon**. La mesure est écartée, et un événement `doublon` est publié ;
- **plus de 32768** (choix B1, hors contrat) : le compteur est revenu en arrière, à cause d'un redémarrage du nœud ou d'une trame en retard. La mesure est gardée, et un événement `retour_seq` est publié.

Le dernier seq de chaque nœud est gardé en mémoire par Node-RED. Il repart de zéro à chaque redémarrage de Node-RED, et la première trame suivante n'est alors pas contrôlée.

**Sorties**

| Topic | Contenu | Utilisé par |
|---|---|---|
| `pce92/mesures/<node_id>` | les mesures acceptées | stockage (S3), moteur d'alerte (B2), tableaux de bord |
| `pce92/evenements` | rejets, doublons, trames perdues, retours de seq | vue technique, diagnostic |

## Installation

**1. Indiquer à Node-RED où se trouve le décodeur**, une seule fois. Ouvrir `settings.js` dans le dossier de Node-RED (Windows : `C:\Users\<nom>\.node-red\settings.js` ; Raspberry Pi : `~/.node-red/settings.js`). Chercher la ligne qui commence par `functionGlobalContext: {` (**pas** celle qui est dans le commentaire au-dessus), et ajouter juste en dessous :

```js
    functionGlobalContext: {
        codec: require("C:/Users/<nom>/Documents/projet-commande-d-entreprise-/trame/decodeur/codec.js"),
```

Le chemin s'écrit avec des `/`, même sous Windows. Redémarrer ensuite Node-RED (Ctrl+C dans son terminal, puis `node-red`). Il faut aussi le redémarrer à chaque modification de `codec.js`.

**2. Importer le flux** : menu ☰ → *Import* → *select a file to import* → `s2_reception.json` → *Import*, puis **Deploy**.

**3. Tester avec l'injecteur** (Mosquitto lancé) : `py injecteur.py --scenario trame_perdue`, puis `--scenario doublon`. Les mesures apparaissent dans l'onglet debug de Node-RED, et les événements aussi (3 trames perdues, 1 doublon).

Comme le dernier seq est mémorisé, relancer un scénario qui repart de seq 1 produit un événement `retour_seq` : c'est normal. Pour l'éviter, utiliser `--seq-depart` ou un autre `--node-id`.
