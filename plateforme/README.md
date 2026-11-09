# Plateforme Node-RED : flux, stockage, tableaux de bord

**Binôme :** B1 Passerelle & plateforme

Flux Node-RED qui reçoivent les trames brutes publiées dans MQTT (`pce92/uplink`) par le récepteur LoRa, les décodent, les stockent et les affichent. Contrat d'interface v1.2 (V1).

Structure proposée :

```
plateforme/
├── flows/          # exports JSON des flux Node-RED (S2 réception) — voir flows/README.md
├── stockage/       # schéma de la base, requêtes
├── injecteur/      # script PC qui publie des trames de test dans MQTT (S5)
└── dashboards/     # vue simple (non technique) et vue technique
```

L'injecteur permet de tester la plateforme sans récepteur ni ESP32.
