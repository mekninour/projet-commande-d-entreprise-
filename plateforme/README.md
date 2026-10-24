# Plateforme Node-RED : flux, stockage, tableaux de bord

**Binôme :** B1 Passerelle & plateforme

Flux Node-RED qui reçoivent les trames décodées par ChirpStack (MQTT), les stockent et les affichent.

Structure proposée :

```
plateforme/
├── flows/          # exports JSON des flux Node-RED (sans identifiants : flows_cred.json est ignoré)
├── stockage/       # schéma de la base, requêtes
├── injecteur/      # script PC qui publie des trames de test dans MQTT au format ChirpStack
└── dashboards/     # vue simple (non technique) et vue technique
```

L'injecteur permet de tester la plateforme sans passerelle ni ESP32.
