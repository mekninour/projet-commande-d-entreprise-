# Flux Node-RED

**Binôme :** B1 – Nour Mekni

| Fichier | Tâche | Rôle |
|---|---|---|
| `s2_reception.json` | S2 | Reçoit les trames brutes, les décode, contrôle `seq` et publie des mesures propres |
| `s3_stockage.json` | S3 | Enregistre les mesures et les événements dans SQLite, recharge les 7 derniers jours au démarrage, et expose une API de lecture |
| `s3_schema.sql` | S3 | Le schéma de la base, pour référence (il est aussi créé automatiquement par le flux) |

## S2 – Réception des trames

```
pce92/uplink ─────────────────────────┐
 (trame brute, point à point)         ▼
application/+/device/+/event/up ──► 0. Lire ChirpStack ──► 1. Décoder (codec S1) ──► 2. Contrôler seq ──► pce92/mesures/<node_id>
 (uplink ChirpStack, LoRaWAN privé)                              │ rejet                   │ doublon, pertes
                        └─────────────┬───────────┘
                                      ▼
                               pce92/evenements
```

**Entrées** : deux topics, traités de la même façon à partir de l'étape 1.
- `pce92/uplink`, publié par un récepteur LoRa point à point (ou par l'injecteur S5) :
  `{ "received_at", "payload_hex", "rssi", "snr", "source" }`.
- `application/+/device/+/event/up`, publié par **ChirpStack** (LoRaWAN privé, validé par le client).

**Étape 0 – Lire ChirpStack.** L'uplink ChirpStack est remis au format ci-dessus :
- `payload_hex` : le champ `data` (base64) converti en hexadécimal. Le champ `object` (rempli si le codec est aussi installé dans ChirpStack) est ignoré : la trame est décodée une seule fois, par le même codec S1, quelle que soit la voie ;
- `received_at` : l'heure de la passerelle (`time`, ou `gwTime`), sinon celle du serveur ChirpStack (`nsTime`), sinon celle de Node-RED (règle 4) ;
- `rssi`, `snr` : la meilleure réception de `rxInfo`. ChirpStack a déjà supprimé les réceptions en double entre passerelles ;
- `source` : `chirpstack`, plus `dev_eui` et `fcnt` pour le diagnostic.

**À régler dans ChirpStack (A3-A5)** : l'intégration MQTT doit publier en **JSON** (`json=true` dans la section `[integration.mqtt]` de `chirpstack.toml` ; c'est déjà le réglage de `chirpstack-docker`, à vérifier sur le Pi), sur le broker auquel Node-RED est abonné.

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

**Étape 2 – Contrôler seq** (règle 5 du contrat), pour chaque nœud. L'écart vaut (seq − dernier seq) modulo 65536 :
- **1** : trame normale ;
- **plus de 1** : des trames ont été perdues. La mesure est gardée, et un événement `trames_perdues` est publié ;
- **0** : c'est un **doublon**. La mesure est écartée, et un événement `doublon` est publié ;
- **plus de 32768** : la trame est **plus ancienne** que la dernière reçue. Trois cas :
  - ce seq a déjà été reçu, avec la même trame : **doublon arrivé en retard**. La mesure est écartée, et un événement `doublon` est publié avec `en_retard: true` ;
  - ce seq avait été compté comme perdu : **trame reçue en retard** (le capteur renvoie ses mesures après une coupure radio). Elle n'est **pas** publiée sur `pce92/mesures` : le contrat v1.2 ne donne pas l'heure de mesure, et une ancienne mesure ne doit pas déclencher une alerte nouvelle (L1, annexe A). Elle est publiée dans un événement `trame_en_retard`, avec sa mesure et une **heure de mesure estimée** (dernière trame reçue − retard × `next_min`). Elle est donc gardée dans le journal des événements, et elle ne compte plus comme perdue ;
  - sinon : **retour en arrière du compteur** (redémarrage du nœud, choix B1 hors contrat). La mesure est gardée, un événement `retour_seq` est publié, et la mémoire du nœud repart de cette trame.

Node-RED garde en mémoire, pour chaque nœud, le dernier seq, les **64 dernières trames reçues** et les seq perdus récents. Une trame plus ancienne que ces 64 trames est traitée comme un redémarrage. Cette mémoire repart de zéro à chaque redémarrage de Node-RED, et la première trame suivante n'est alors pas contrôlée.

**Sorties**

| Topic | Contenu | Utilisé par |
|---|---|---|
| `pce92/mesures/<node_id>` | les mesures acceptées | stockage (S3), moteur d'alerte (B2), tableaux de bord |
| `pce92/evenements` | rejets, doublons (immédiats ou en retard), trames perdues, trames reçues en retard, retours de seq | stockage (S3), vue technique, diagnostic |

## Installation

**1. Indiquer à Node-RED où se trouve le décodeur**, une seule fois. Ouvrir `settings.js` dans le dossier de Node-RED (Windows : `C:\Users\<nom>\.node-red\settings.js` ; Raspberry Pi : `~/.node-red/settings.js`). Chercher la ligne qui commence par `functionGlobalContext: {` (**pas** celle qui est dans le commentaire au-dessus), et ajouter juste en dessous :

```js
    functionGlobalContext: {
        codec: require("C:/Users/<nom>/Documents/projet-commande-d-entreprise-/trame/decodeur/codec.js"),
```

Le chemin s'écrit avec des `/`, même sous Windows. Redémarrer ensuite Node-RED (Ctrl+C dans son terminal, puis `node-red`). Il faut aussi le redémarrer à chaque modification de `codec.js`.

**2. Importer le flux** : menu ☰ → *Import* → *select a file to import* → `s2_reception.json` → *Import*, puis **Deploy**.

**3. Tester avec l'injecteur** (Mosquitto lancé), depuis `plateforme/injecteur`. Chaque scénario marche aussi en LoRaWAN avec `--format chirpstack` (même résultat, `source` = `chirpstack`) :
- `py injecteur.py --scenario trame_perdue` : 3 événements `trames_perdues` ;
- `py injecteur.py --scenario doublon` : 1 événement `doublon` en retard (seq 4) ;
- `py injecteur.py --scenario retransmission_differee` : 3 trames perdues, puis 1 doublon en retard (seq 4) et 3 événements `trame_en_retard` (seq 5 à 7). Les seq 5 à 7 n'apparaissent pas dans les mesures.

Les événements s'affichent dans l'onglet debug de Node-RED, et dans la vue technique.

**4. Tests sans Node-RED** : `node test_s2.js`, depuis ce dossier. Le test lit les fonctions de `s2_reception.json` et les exécute sur des suites de trames (pertes, doublons immédiats et en retard, trames en retard, redémarrage du nœud) et sur des uplinks ChirpStack.

## S3 – Stockage de l'historique

```
pce92/mesures/+  ──► INSERT mesures    ──┐
pce92/evenements ──► INSERT evenements ──┼──► pce92.db (SQLite)
                                         │
au démarrage ◄── lecture des 7 derniers jours ──► tableaux de bord (courbes rechargées)
GET /pce92/mesures ◄── lecture à la demande (JSON ou CSV)
```

**Pourquoi SQLite.** La base tourne sur le Raspberry Pi de la passerelle : peu de puissance, une carte SD, des coupures de courant possibles, pas toujours internet. Le volume est minuscule : 48 mesures par jour et par capteur, soit moins de 4 Mo par an. SQLite est un **simple fichier**, sans serveur à installer ni à administrer. Il résiste bien aux coupures (mode WAL), et il se sauvegarde en copiant le fichier. Il répond donc à la demande du client d'une solution simple et réparable. InfluxDB ou PostgreSQL seraient des serveurs de plus à faire tourner, pour rien à cette échelle.

**Tables** (détail dans `s3_schema.sql`) :

| Table | Une ligne par… | Colonnes principales |
|---|---|---|
| `mesures` | mesure acceptée par S2 | `node_id`, `received_at` (UTC), `water_mm` (NULL si invalide), `water_valid`, `batt_v`, `seq`, `alert`, `next_min`, `lost_before`, `rssi`, `snr`, `source`, `payload_hex` |
| `evenements` | incident publié par S2 | `received_at`, `type` (trames_perdues, doublon, rejet, retour_seq), `node_id`, `seq`, `details` (JSON) |

Une même mesure (même capteur, même heure, même seq) n'est jamais enregistrée deux fois (contrainte `UNIQUE` + `INSERT OR IGNORE`).

**Le flux en 4 parties** (onglet « S3 – Stockage de l'historique ») :
1. **Au démarrage** : crée les tables si elles n'existent pas, puis relit les mesures et les événements des 7 derniers jours et les renvoie aux tableaux de bord. Les courbes et les compteurs ne repartent plus de zéro après un redémarrage.
2. **Enregistrement** : chaque mesure et chaque événement publiés par S2 sont écrits dans la base.
3. **Requête « 7 derniers jours »** : le bouton *7 jours – capteur 3* affiche dans le debug le nombre de mesures, la première et la dernière.
4. **API de lecture** : `GET /pce92/mesures` dans un navigateur, par exemple :
   - http://localhost:1880/pce92/mesures?node_id=3&jours=7 → JSON
   - http://localhost:1880/pce92/mesures?node_id=3&jours=7&format=csv → fichier CSV (export, par exemple pour OPALimpact)
   - sans `node_id` → tous les capteurs ; `jours` vaut 7 par défaut (366 au maximum).

**Installation**

1. Le flux S2 et le flux des tableaux de bord sont déjà importés (S3 réutilise le serveur MQTT de S2 et envoie l'historique aux tableaux de bord). Le module `node-red-node-sqlite` est installé (menu ☰ → *Manage palette*).
2. Menu ☰ → *Import* → `s3_stockage.json` → *Import*.
3. **Adapter le chemin du fichier de base**, une seule fois : double-cliquer sur un nœud *sqlite* (par exemple *INSERT mesures*), puis sur le crayon à côté de *Database*, et indiquer :
   - Windows : `C:/Users/<nom>/.node-red/pce92.db`
   - Raspberry Pi : `/home/<nom>/.node-red/pce92.db`

   Le fichier est créé tout seul au premier démarrage. Il est rangé dans le dossier de Node-RED, **hors du dépôt** : les données ne sont jamais commitées.
4. **Deploy**. Sous les nœuds *sqlite*, un statut vert « RWC » doit apparaître.

**Vérifier**
- Lancer `py injecteur.py --scenario montee --node-id 3`, puis cliquer sur le bouton *7 jours – capteur 3* : le debug affiche `total: 21`.
- Ouvrir http://localhost:1880/pce92/mesures?node_id=3 : les 21 mesures s'affichent en JSON.
- Redémarrer Node-RED (Ctrl+C, puis `node-red`) : les courbes de la vue technique réapparaissent.
- Pour regarder la base à la souris : *DB Browser for SQLite* → ouvrir `pce92.db`.

**Limites**
- Le dernier `seq` de chaque capteur (contrôle des pertes de S2) n'est pas encore relu depuis la base : la première trame après un redémarrage n'est pas contrôlée.
- Pas encore de purge automatique : vu le volume (moins de 4 Mo par an et par capteur), ce n'est pas urgent.
