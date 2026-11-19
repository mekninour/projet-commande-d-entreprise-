# Fiche mémo — ChirpStack

**Auteure :** Nour Mekni (B1)

## À quoi sert ChirpStack ?

C'est le **serveur LoRaWAN** de la chaîne. Il reçoit les trames relayées par la passerelle, vérifie qu'elles viennent d'un capteur connu, les **déchiffre**, les **décode** (codec S1), puis les publie sur MQTT pour Node-RED.

```
ESP32 ──radio──► Passerelle (Pi + RAK) ──UDP 1700──► ChirpStack ──MQTT──► Node-RED
```

## Installer et lancer

```
git clone https://github.com/chirpstack/chirpstack-docker.git
cd chirpstack-docker
docker compose up -d       # démarrer (Docker Desktop doit être ouvert)
docker compose ps          # vérifier : tout doit être "Up"
docker compose stop        # arrêter (start pour relancer)
```

Interface : **http://localhost:8080**, identifiants `admin` / `admin`. Le paquet est déjà réglé pour l'Europe (EU868) et lance aussi **Mosquitto** (MQTT, port 1883).

## Ce qu'on configure

| Élément | Rôle | Réglages du projet |
|---|---|---|
| **Device profile** | le « modèle » de capteur | EU868, LoRaWAN 1.0.3, OTAA, classe A, 1 trame attendue par heure, **codec S1** |
| **Gateway** | la passerelle | son identifiant (EUI), le même que dans la configuration du Pi |
| **Application** | regroupe les capteurs | `pce92-crues` |
| **Device** | un capteur | DevEUI + AppKey, recopiés dans l'émulateur ESP32 |

L'**AppKey** est la clé secrète du capteur : elle ne va **jamais** sur GitHub.

## Ce que ChirpStack publie sur MQTT

| Topic | Contenu |
|---|---|
| `application/<appID>/device/<devEUI>/event/up` | la trame **décodée**, en JSON. C'est celle que lit Node-RED. |
| `eu868/gateway/<gwID>/state/conn` | la passerelle est en ligne ou hors ligne |
| `application/.../event/log` | les erreurs, par exemple un problème de codec |

Dans le JSON `event/up`, les champs utiles sont :
- `time` : l'heure de réception ;
- `deviceInfo.devEui` : quel capteur a envoyé la trame ;
- **`object`** : les valeurs décodées (`node_id`, `water_mm`, `seq`, `alert`…) ;
- `rxInfo` : la qualité du signal (`rssi`, `snr`).

Un message complet est donné en exemple dans [`exemple_event_up.json`](exemple_event_up.json). La trame qu'il contient est l'exemple officiel du contrat.

ChirpStack ne publie **que s'il reçoit une vraie trame**. Pour tester sans matériel, l'injecteur S5 publie des messages au même format.

## Selon ta tâche

**Programmer l'ESP32 (B3)**
- Dans le profil, choisis la **même version LoRaWAN** que ta bibliothèque : LMIC → 1.0.3 ; RadioLib → 1.0.4 ou 1.1.
- Crée le device, puis copie DevEUI, JoinEUI et AppKey dans `secrets.h` (jamais dans le dépôt).
- **Avec LMIC**, DevEUI et JoinEUI s'écrivent **à l'envers** (octet de poids faible en premier). L'AppKey reste dans l'ordre affiché. Une erreur d'ordre fait échouer la connexion sans message clair.
- Pour vérifier : onglet **Events** du device. Un `join` puis des `up` = tout fonctionne. Un join qui n'arrive pas : regarde l'onglet **LoRaWAN frames**.

**Lire les mesures dans Node-RED (B1, B2)**
- Bloc *mqtt in* : serveur `localhost:1883`, topic `application/+/device/+/event/up`, sortie « parsed JSON object ».
- Les valeurs décodées sont dans `msg.payload.object`.

**Envoyer un message au capteur (R6, seuils à distance)**
- À la main : onglet **Queue** du device. Choisis un fPort, saisis les octets, *Enqueue*.
- Par MQTT : publie sur `application/<appID>/device/<devEUI>/command/down` le JSON `{"devEui": "<devEUI>", "confirmed": false, "fPort": 10, "data": "<octets en base64>"}`.
- Le capteur reçoit le message **après sa prochaine émission** (classe A).

**Installer la passerelle (A3 à A5)**
- Voir la partie suivante, et la fiche Raspberry Pi d'Amine (P2e).

## Relier la passerelle

Sur le Raspberry Pi, le fichier `global_conf.json` du packet forwarder indique où envoyer les trames :
- `server_address` : l'adresse de ChirpStack ;
- les ports `1700`.

On déclare ensuite le même identifiant de passerelle dans ChirpStack.

## À retenir

- **node_id** (dans la trame) identifie le **site** ; le **DevEUI** identifie le capteur pour LoRaWAN.
- Pour repérer les trames perdues, on utilise **seq**, pas `fCnt` : `fCnt` repart à 0 à chaque reconnexion du capteur.

## Si ça ne marche pas

| Problème | Vérifier |
|---|---|
| Interface inaccessible | Docker Desktop ouvert, `docker compose ps` |
| Passerelle « Never seen » | adresse et port 1700 côté Pi, même identifiant des deux côtés |
| Le capteur ne se connecte pas | DevEUI et AppKey identiques dans ChirpStack et dans l'ESP32 |
| Pas de valeurs décodées | codec présent dans le profil ; erreurs dans `event/log` |
| Rien dans Node-RED | MQTT Explorer : le message arrive-t-il ? Le topic est-il le bon ? |
