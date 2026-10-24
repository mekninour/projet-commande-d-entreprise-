# Émulateur de nœud ESP32

**Binôme :** B3 Émulateur & campagnes

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

Fiche de formation : [ESP32 + LoRa](../docs/formations/README.md). Bibliothèque LoRaWAN recommandée : RadioLib (choix final par B3).
