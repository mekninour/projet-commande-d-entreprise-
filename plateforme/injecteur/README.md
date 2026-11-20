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

`--format chirpstack` publie à la place un uplink ChirpStack v4 (`application/<app-id>/device/<dev-eui>/event/up`), comme le fera la vraie chaîne en LoRaWAN privé, validé par le client. La réception S2 lit les deux formats.

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
| `--seq-depart` | la suite du dernier seq | le premier numéro de trame (voir « Numéros de trame » ci-dessous) |
| `--seuil` | 300 mm | le seuil d'alerte du nœud (bit 0 levé à partir de ce niveau) |
| `--periode` | 30 min | l'écart entre deux trames, envoyé dans `next_min` (fréquence fixe en V1) |
| `--vitesse` | 900 | l'accélération : 900 = 30 min simulées en 2 s ; 1 = temps réel |
| `--coupure` | 0 | `trame_perdue` seulement : ajoute une coupure de N trames perdues d'affilée |
| `--graine` | 92 | la graine du hasard : la même graine donne toujours les mêmes pertes et les mêmes mesures |
| `--apercu` | — | affiche les messages au lieu de les publier |

**Horodatage.** En temps accéléré, les heures de réception sont simulées et le scénario **se termine maintenant**. On obtient un historique récent, sans date dans le futur. En temps réel (`--vitesse 1`), le scénario démarre maintenant. Les trames sont émises à intervalle régulier, comme un vrai capteur (`next_min`) : en accéléré, une toutes les 2 s, mais leurs heures de réception restent espacées de 30 min.

**Numéros de trame.** Comme un vrai capteur, l'injecteur continue son compteur : il garde le dernier `seq` envoyé pour chaque nœud dans `.seq_injecteur.json` (fichier local, pas dans git), et le scénario suivant repart du seq suivant. Sans cela, relancer un scénario renverrait des seq déjà reçus, que la réception S2 prendrait pour des doublons en retard. `--seq-depart 1` force un départ à 1 : S2 y verra un retour en arrière du compteur, ou des doublons si les mêmes trames ont été reçues récemment.

**Temps d'exécution.** En accéléré, compter 2 s par trame : `trame_perdue` dure environ 40 s, `montee` 40 s, `retransmission_differee` 25 s. Un script qui lance l'injecteur doit attendre la fin (pas de délai maximal plus court).

## Scénarios

| Scénario | Ce qu'il simule | Ce qu'il permet de tester |
|---|---|---|
| `normal` | 12 trames autour de 30 mm | la réception, le stockage, l'affichage |
| `montee` | une crue lente qui dépasse 300 mm puis redescend | l'alerte et son retour à la normale |
| `montee_rapide` | +120 mm par trame | une montée brutale |
| `pic` | une seule mesure au-dessus du seuil | une alerte isolée |
| `trame_perdue` | 20 trames, dont 3 pertes isolées au hasard (collisions radio) ; avec `--coupure N`, en plus N trames perdues d'affilée (passerelle ou lien radio coupé) | la détection de pertes (écart de seq > 1) |
| `doublon` | la trame seq 4, déjà reçue, revient après la seq 7, à l'identique | la détection d'un doublon arrivé en retard |
| `retransmission_differee` | coupure radio (seq 5 à 7 perdues), puis le capteur renvoie ses 4 dernières mesures (seq 4 à 7) après la seq 9 | un doublon en retard (seq 4) et des trames reçues en retard (5 à 7), qui ne doivent pas être prises pour des mesures actuelles |
| `capteur_muet` | 5 trames puis silence | la détection d'un capteur muet grâce à `next_min` |
| `mesure_invalide` | 2 trames avec `water_mm` = 0xFFFF | qu'une mesure invalide n'est pas prise pour un niveau |
| `batterie_faible` | une batterie qui descend de 3,30 à 2,85 V, puis inconnue (0xFF) | l'affichage de la batterie |

Les scénarios sont dans `scenarios.py`. Pour en ajouter un, on écrit une fonction qui renvoie une liste d'étapes, puis on l'ajoute au dictionnaire `SCENARIOS`. Une étape `{"renvoi": i}` réémet plus tard la trame de l'étape `i`, à l'identique.

**Pourquoi des doublons « en retard ».** Avec LoRaWAN, ChirpStack supprime déjà les doublons quand plusieurs passerelles reçoivent la même trame (L1, § 2.1). Un doublon qui atteint Node-RED vient plutôt d'un capteur qui renvoie ses mesures stockées après une coupure radio (L1, annexe A, § 2.1) : il arrive plus tard, après d'autres trames. C'est le cas qu'il faut tester.
