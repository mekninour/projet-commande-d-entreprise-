# Plateforme : réception, stockage, alertes, tableaux de bord

**Binôme :** B1 Passerelle & plateforme

La plateforme reçoit les trames des capteurs (contrat d'interface v1.2), les décode, les contrôle, les enregistre, calcule l'état d'alerte de chaque site et l'affiche.

**Installer sur le Raspberry Pi : [`INSTALLATION.md`](INSTALLATION.md)** (un script fait l'essentiel).

```
ChirpStack (LoRaWAN privé) ── application/+/device/+/event/up ──┐
Injecteur S5 (tests sur PC) ── pce92/uplink ou format ChirpStack ┤
                                                                ▼
                                  S2 réception ── pce92/mesures/<n°>, pce92/evenements
                                       │                 │                      │
                                  S3 base SQLite    moteur d'alerte (B2)   tableaux de bord
                                  (historique)      pce92/alertes/<n°> ──►  AL5, AL6, Historique
```

| Dossier | Contenu | Tâches |
|---|---|---|
| [`flows/`](flows/) | Flux Node-RED : réception (S2) et stockage (S3), avec leurs tests | S2, S3 |
| [`dashboards/`](dashboards/) | Vue simple, vue technique, page Historique | AL5, AL6 |
| [`config/`](config/) | Moteur d'alerte et seuils par capteur (`seuils.csv`) | B2 |
| [`injecteur/`](injecteur/) | Script PC qui publie des trames de test dans MQTT, sans émulateur ni passerelle | S5 |
| [`installer_pi.sh`](installer_pi.sh) | Installation sur le Pi (voir `INSTALLATION.md`) | D1 |

Le décodeur des trames (codec S1) est dans [`../trame/decodeur/`](../trame/decodeur/).
