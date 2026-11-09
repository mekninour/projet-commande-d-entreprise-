# Injecteur de trames de test (S5)

**Binôme :** B1 – Nour Mekni

Script Python qui **simule la réception de trames capteur** et les publie dans MQTT. On peut ainsi tester Node-RED, le stockage, les alertes et les tableaux de bord **sans ESP32 ni récepteur**. Les trames suivent le **contrat d'interface v1.2 (V1)**.

## Format publié

Par défaut (`--format brut`), l'injecteur publie ce que publiera le **récepteur LoRa point à point** de la V1 :

- topic : `pce92/uplink`
- message :

```json
{ "received_at": "2026-11-09T10:00:00.000Z", "payload_hex": "0003013682009D0105000000",
  "rssi": -94, "snr": 0.3, "source": "injecteur" }
```

| Champ | Contenu |
|---|---|
| `received_at` | heure de réception (UTC) : c'est l'horodatage de la mesure (règle 4 du contrat) |
| `payload_hex` | les 12 octets de la trame, en hexadécimal |
| `rssi`, `snr` | qualité du signal radio |
| `source` | `injecteur` ici ; le vrai récepteur mettra son propre nom |

**Ce format est une proposition de B1** pour le récepteur, à valider avec Amine. Le décodage se fait ensuite dans Node-RED, avec `trame/decodeur/codec.js`.

`--format chirpstack` publie à la place l'ancien format ChirpStack v4 (`application/.../event/up`, décodé par le codec S1). Il est gardé au cas où la chaîne repasserait en LoRaWAN.

## Prérequis

- Python 3 et `paho-mqtt` : `py -m pip install paho-mqtt`
- Un broker MQTT : le Mosquitto de `chirpstack-docker` (port 1883), ou un Mosquitto local
- Node.js, seulement pour les tests et le format `chirpstack`

## Utilisation

Depuis ce dossier :

```
py injecteur.py --liste                       # les scénarios disponibles
py injecteur.py --scenario montee             # publie le scénario
py injecteur.py --scenario normal --apercu    # affiche les messages sans publier
py test_injecteur.py                          # tests, sans broker
```

| Option | Défaut | Rôle |
|---|---|---|
| `--scenario` | — | le scénario à rejouer (voir ci-dessous) |
| `--format` | `brut` | `brut` (V1) ou `chirpstack` |
| `--hote`, `--port` | `localhost`, `1883` | le broker MQTT |
| `--node-id` | 3 | le site, écrit dans la trame |
| `--seuil` | 300 mm | le seuil d'alerte du nœud (bit 0 levé à partir de ce niveau) |
| `--periode` | 30 min | l'écart entre deux trames, envoyé dans `next_min` (fréquence fixe en V1) |
| `--vitesse` | 900 | l'accélération : 900 = 30 min simulées en 2 s ; 1 = temps réel |
| `--apercu` | — | affiche les messages au lieu de les publier |

**Horodatage.** En temps accéléré, les heures de réception sont simulées et le scénario **se termine maintenant**. On obtient un historique récent, sans date dans le futur. En temps réel (`--vitesse 1`), le scénario démarre maintenant.

## Scénarios

| Scénario | Ce qu'il simule | Ce qu'il permet de tester |
|---|---|---|
| `normal` | 12 trames autour de 30 mm | la réception, le stockage, l'affichage |
| `montee` | une crue lente qui dépasse 300 mm puis redescend | l'alerte et son retour à la normale |
| `montee_rapide` | +120 mm par trame | une montée brutale |
| `pic` | une seule mesure au-dessus du seuil | une alerte isolée |
| `trame_perdue` | 3 trames perdues | la détection de pertes (écart de seq > 1) |
| `doublon` | une trame reçue 2 fois | la détection de doublons (écart de seq = 0) |
| `capteur_muet` | 5 trames puis silence | la détection d'un capteur muet grâce à `next_min` |
| `mesure_invalide` | 2 trames avec `water_mm` = 0xFFFF | qu'une mesure invalide n'est pas prise pour un niveau |
| `batterie_faible` | une batterie qui descend de 3,30 à 2,85 V, puis inconnue (0xFF) | l'affichage de la batterie |

Les scénarios sont dans `scenarios.py`. Pour en ajouter un, on écrit une fonction qui renvoie une liste d'étapes, puis on l'ajoute au dictionnaire `SCENARIOS`.
