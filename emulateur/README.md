# Émulateur de nœud ESP32

Code de la carte ESP32 + LoRa qui se fait passer pour le nœud de Brest : elle rejoue des séries de hauteur d'eau, construit la trame de 12 octets et l'envoie en LoRaWAN selon trois modes (naïf, fréquence fixe, S4 hybride).

Projet **PlatformIO** (versions des bibliothèques fixées dans `platformio.ini`). Structure proposée :

```
emulateur/
├── platformio.ini
├── include/
│   ├── secrets.example.h   # modèle des clés LoRaWAN (à copier en secrets.h, jamais commité)
│   └── config.h            # mode d'émission, intervalle, scénario
├── src/                    # main, pile LoRaWAN, rejeu, modes, compteurs
└── test/                   # tests unitaires (pio test)
```

Fiche de formation : [ESP32 + LoRa (P2d)](../docs/formations/README.md). Bibliothèque LoRaWAN recommandée : RadioLib (choix final en E2).

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| E2 | Pile LoRaWAN sur ESP32 | Bibliothèque choisie, join OTAA, trame reçue dans ChirpStack | Brahima Diarrassouba | E1, A5 | Après |
| E4 | Rejeu des séries | Lecture d'un scénario, horloge accélérée réglable, README | Mathéo Vignaud | E3 (format) | Stretch |
| E5 | Modes d'émission | 3 modes : naïf, fréquence fixe, S4 hybride | Brahima Diarrassouba | E1, E4 | Après |
| E6 | Compteurs embarqués | Trames, octets, temps d'émission et d'éveil, export série | Mathéo Vignaud | E5 | Après |
| R3 | Conservation côté nœud | Mémoire tampon si radio perdue, rattrapage étalé | Gaetan Boulard | E5 | Après |
| R4 | Test perte radio | Perte puis reprise, journal | Brahima Diarrassouba | R3 | Après |

État à jour : voir les issues GitHub correspondantes.
