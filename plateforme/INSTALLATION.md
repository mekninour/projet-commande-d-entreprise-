# Installer la plateforme sur le Raspberry Pi

Ce guide branche la plateforme (réception, stockage, moteur d'alerte, tableaux de bord) sur la passerelle LoRaWAN : les trames de l'émulateur, reçues par ChirpStack, s'affichent dans les tableaux de bord. Compter **20 minutes**.

```
Émulateur ESP32 ──radio──► Passerelle RAK ──► ChirpStack ──MQTT (localhost:1883)──► Node-RED : S2 réception ─► S3 base
                                                                                         │              └─► moteur d'alerte
                                                                                         └──► tableaux de bord ◄──┘
```

Tout tourne sur le Pi et passe par le broker MQTT de ChirpStack (`localhost:1883`) : aucun réglage réseau.

## 0. Avant de commencer

- ChirpStack tourne sur le Pi et **reçoit déjà les trames de l'émulateur** : elles apparaissent dans l'interface de ChirpStack (`http://<IP du Pi>:8080`), appareil → onglet *Events*, lignes `up`.
- L'intégration MQTT de ChirpStack publie en **JSON** (`json=true` dans `[integration.mqtt]` de `chirpstack.toml` ; c'est le réglage par défaut de `chirpstack-docker`).
- Le codec S1 n'a **pas** besoin d'être installé dans ChirpStack : Node-RED décode lui-même la trame (champ `data`).
- On travaille sur le Pi, dans un terminal (écran et clavier, ou `ssh`).

## 1. Récupérer le dépôt sur le Pi

Première fois :
```bash
cd ~
git clone https://github.com/mekninour/projet-commande-d-entreprise-.git
cd projet-commande-d-entreprise-
```
Déjà cloné :
```bash
cd ~/projet-commande-d-entreprise-
git checkout main
git pull
```

## 2. Lancer le script d'installation

```bash
bash plateforme/installer_pi.sh
```

Il fait tout dans l'ordre et affiche `OK` à chaque étape : modules Node-RED, décodeur, flux, moteur d'alerte, puis déploiement dans Node-RED. **Les flux déjà présents dans Node-RED sont gardés.** On peut le relancer sans risque.

S'il s'arrête sur `STOP`, il dit quoi faire. Les deux cas habituels :
- **Node-RED n'est pas installé** : le script donne la commande officielle d'installation. Ensuite : `node-red-start`, attendre « Started flows », `node-red-stop`, et relancer le script.
- **Mot de passe** : le script demande celui du Pi pour installer `python3-paho-mqtt` (une seule fois).

## 3. Lancer le moteur d'alerte

Dans un **deuxième terminal**, depuis la racine du dépôt (le moteur y cherche `plateforme/config/seuils.csv`) :
```bash
cd ~/projet-commande-d-entreprise-
python3 plateforme/config/moteur_alerte.py
```
Il affiche `[MQTT] Connecté au broker localhost:1883`, puis une ligne `[PUBLIÉ] pce92/alertes/<n°>` à chaque trame. Le laisser tourner. Pour qu'il démarre tout seul avec le Pi, voir l'étape 6.

## 4. Vérifier que les trames arrivent

1. Trouver l'adresse du Pi : `hostname -I` (le premier nombre, par exemple `192.168.1.42`).
2. Ouvrir `http://<IP du Pi>:1880` (depuis le Pi : `http://localhost:1880`), onglet **S2 – Réception des trames**. À la trame suivante de l'émulateur :
   - sous **0. Lire ChirpStack** : le devEui et le `fCnt` de l'émulateur ;
   - sous **2. Contrôler seq** : `nœud <n°> · seq <n°>` en vert.
3. Ouvrir `http://<IP du Pi>:1880/dashboard` :
   - **Vue simple** : une carte par site, NORMAL ou ALERTE ;
   - **Vue technique** : le capteur, sa dernière trame « il y a quelques secondes », sa courbe ;
   - **Historique** : les mesures enregistrées, export CSV.

Si la carte affiche « calcul de secours (moteur absent) », le moteur de l'étape 3 ne tourne pas.

## 5. Le site et le seuil de chaque capteur

Ils sont dans `plateforme/config/seuils.csv` (une ligne par capteur : `node_id,site,seuil_alerte`, seuil en mm). Le `node_id` est celui que l'émulateur écrit dans sa trame. **Un capteur absent de ce fichier n'a pas d'état d'alerte.** Le moteur relit le fichier à chaque mesure : une modification s'applique sans rien redémarrer.

Les autres réglages du moteur (persistance, hystérésis, montée rapide, filtre des valeurs aberrantes) sont dans `plateforme/config/parametres_alerte.json`, et peuvent être changés capteur par capteur dans `seuils.csv`. Voir [`config/PARAMETRES.md`](config/PARAMETRES.md).

## 6. Démarrage automatique (facultatif)

Node-RED :
```bash
sudo systemctl enable nodered.service
```
Moteur d'alerte :
```bash
sudo tee /etc/systemd/system/pce92-moteur.service >/dev/null <<EOF
[Unit]
Description=PCE 92 - moteur d'alerte
After=network-online.target

[Service]
User=$USER
WorkingDirectory=$HOME/projet-commande-d-entreprise-
ExecStart=/usr/bin/python3 -u plateforme/config/moteur_alerte.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now pce92-moteur.service
```
Son journal : `journalctl -u pce92-moteur -f`.

## 7. Mettre à jour après un changement sur GitHub

```bash
cd ~/projet-commande-d-entreprise-
git pull
bash plateforme/installer_pi.sh
```
Puis redémarrer le moteur (Ctrl+C et relancer, ou `sudo systemctl restart pce92-moteur`). Les mesures déjà enregistrées sont gardées.

## En cas de problème

| Symptôme | Cause probable | Que faire |
|---|---|---|
| Rien sous « 0. Lire ChirpStack » | ChirpStack ne publie pas sur MQTT, ou pas en JSON | `mosquitto_sub -t "application/#" -v` sur le Pi : le message `event/up` doit s'afficher à chaque trame. Sinon, régler l'intégration MQTT de ChirpStack. |
| `codec absent` sous « 1. Décoder » | Node-RED n'a pas été redémarré après le script | `node-red-restart` |
| Trame rejetée (`rejet` dans les événements) | La trame ne suit pas le contrat v1.2 (12 octets) | Comparer avec `trame/exemples/exemples_trames.csv` et le contrat (`docs/contrat_interface.md`) |
| Pas de point vert « connected » sous les nœuds MQTT | Le broker n'est pas sur `localhost:1883` | Onglet S2, nœud « Uplinks ChirpStack » → crayon à côté de *Server* → mettre l'adresse du broker → *Update* → **Deploy** |
| « calcul de secours (moteur absent) » | Le moteur d'alerte ne tourne pas | Étape 3 |
| Pas d'état d'alerte pour un capteur | `node_id` absent de `seuils.csv` | Étape 5 |
| Tableau de bord vide après un redémarrage | Normal pendant quelques secondes : il recharge les 7 derniers jours | Attendre, puis F5 |

Pour aller plus loin : [`flows/README.md`](flows/README.md) (réception et stockage), [`dashboards/README.md`](dashboards/README.md) (tableaux de bord), [`injecteur/README.md`](injecteur/README.md) (tester sans émulateur).
