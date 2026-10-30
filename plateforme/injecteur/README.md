# Injecteur de trames de test (S5)

**Binôme :** B1 – Nour Mekni

Script Python qui **se fait passer pour ChirpStack**. Il publie dans MQTT des messages `event/up` au même format que ChirpStack v4. On peut ainsi tester Node-RED, le stockage, les alertes et les dashboards **sans ESP32 ni passerelle**.

Pour chaque trame, il :
1. fabrique les 12 octets selon le contrat ;
2. les décode avec le codec S1 (`trame/decodeur/codec.js`), comme ChirpStack ;
3. publie le JSON sur `application/<app_id>/device/<dev_eui>/event/up`.

## Prérequis

- Python 3 et `paho-mqtt` : `py -m pip install paho-mqtt`
- Node.js, pour exécuter le codec S1
- Un broker MQTT : le Mosquitto de `chirpstack-docker` (port 1883), ou un Mosquitto local

## Utilisation

Depuis ce dossier :

```
py injecteur.py --liste                              # les scénarios disponibles
py injecteur.py --scenario montee                    # publie le scénario
py injecteur.py --scenario normal --apercu           # affiche les messages sans publier
py injecteur.py --scenario montee --app-id <id> --dev-eui <devEUI>   # mêmes identifiants que dans ChirpStack
py test_injecteur.py                                 # tests, sans broker
```

| Option | Défaut | Rôle |
|---|---|---|
| `--scenario` | — | le scénario à rejouer (voir ci-dessous) |
| `--hote`, `--port` | `localhost`, `1883` | le broker MQTT |
| `--app-id`, `--dev-eui` | valeurs fictives | à remplacer par ceux de ChirpStack pour un topic identique |
| `--node-id` | 3 | le site, écrit dans la trame |
| `--seuil` | 2000 mm | le seuil d'alerte embarqué du nœud (il lève le bit d'alerte) |
| `--intervalle` | 1800 s | l'écart simulé entre deux trames (contrat : 30 min) |
| `--vitesse` | 900 | l'accélération : 900 = 30 min simulées en 2 s ; 1 = temps réel |
| `--apercu` | — | affiche les messages au lieu de les publier |

**Horodatage.** En temps accéléré, les heures de réception (`time`) sont simulées et le scénario **se termine maintenant**. On obtient un historique récent, sans date dans le futur. En temps réel (`--vitesse 1`), le scénario démarre maintenant.

## Scénarios

| Scénario | Ce qu'il simule | Ce qu'il permet de tester |
|---|---|---|
| `normal` | 12 trames, niveau stable | la réception, le stockage, l'affichage |
| `montee` | une crue lente qui dépasse le seuil puis redescend | les paliers, la persistance, la marge de retour |
| `montee_rapide` | +400 mm par trame | la règle de montée rapide |
| `pic` | une seule mesure aberrante | qu'il n'y a **pas** d'alerte (persistance) |
| `trame_perdue` | 3 trames perdues (trou dans `seq`) | la détection de pertes |
| `doublon` | une trame publiée 2 fois | qu'on ne stocke qu'une fois |
| `capteur_muet` | 5 trames puis silence | l'alerte « hors ligne » |
| `batterie_faible` | une batterie qui descend, mode éco sous 3,0 V | la vue technique, le bit éco |
| `defaut_capteur` | 2 trames avec le bit défaut et un niveau à 0 | qu'un défaut n'est pas pris pour une décrue |

Les scénarios sont dans `scenarios.py`. Pour en ajouter un, on écrit une fonction qui renvoie une liste d'étapes, puis on l'ajoute au dictionnaire `SCENARIOS`.

## Limites

- Les octets 8 à 11 sont à zéro : pas d'agrégation S4 tant que le format n'est pas validé.
- `fCnt` est égal à `seq`, et `rssi`/`snr` sont tirés au hasard : ces valeurs servent seulement à l'affichage.
- Les hypothèses de la trame (20 mV par unité, alerte 0x80, défaut 0x40, éco 0x20) sont les mêmes que dans le codec S1.
