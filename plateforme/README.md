# Plateforme Node-RED : flux, stockage, tableaux de bord

Flux Node-RED qui reçoivent les trames décodées par ChirpStack (MQTT), les stockent et les affichent.

Structure proposée :

```
plateforme/
├── flows/          # exports JSON des flux Node-RED (sans identifiants : flows_cred.json est ignoré)
├── stockage/       # S3 : schéma de la base, requêtes
├── injecteur/      # S5 : script PC qui publie des trames de test dans MQTT au format ChirpStack
└── dashboards/     # AL5 (vue simple), AL6 (vue technique)
```

L'injecteur S5 permet à B2 de travailler sur les alertes sans passerelle ni ESP32.

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| S2 | Flux vers Node-RED | Abonnement MQTT, extraction des champs, horodatage passerelle | Nour Mekni | A4 (ou Mosquitto local) | Stretch |
| S3 | Stockage de l'historique | Base choisie et justifiée, requête 7 jours | Nour Mekni | S2 | Après |
| S4 | Test de bout en bout | Trame ESP32 affichée dans Node-RED, capture et log | Brahima Diarrassouba + Mohamed Amine Dahbi | E2, S1, S2 | Après |
| S5 | Injecteur de trames de test | Script PC publiant dans MQTT au format ChirpStack | Nour Mekni | — | Socle |
| AL5 | Vue simple (couleurs) | Dashboard non technique par palier | Nour Mekni | S3, AL2 | Après |
| AL6 | Vue technique | Courbes, état capteurs/batteries | Nour Mekni | S3 | Après |

État à jour : voir les issues GitHub correspondantes.
