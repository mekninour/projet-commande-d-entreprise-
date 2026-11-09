# Trame de 12 octets : encodeur, décodeur, exemples

**Binôme :** B2 (encodeur) et B1 (décodeur)

Ce dossier est **l'interface entre les binômes** et avec Brest. Il contient la seule définition de la trame dans le code, conforme au [contrat d'interface](../docs/contrat_interface.md).

Structure proposée :

```
trame/
├── encodeur/       # encodage C/C++ (réutilisé par l'émulateur), tests unitaires
├── decodeur/       # décodeur JavaScript (Node-RED, ou ChirpStack si LoRaWAN), tests
└── exemples/       # trames de référence partagées (CSV) : chaque encodeur et décodeur doit les passer
```

Règle : **toute nouvelle trame de test va dans `exemples/exemples_trames.csv`**, et les tests de l'encodeur et du décodeur la relisent. Ainsi l'encodeur et le décodeur ne peuvent pas diverger.

Référence : **contrat d'interface v1.2 (V1)** reçu de Brest — batterie `batt_5mv` (2,50 V + n × 5 mV), alerte sur le bit 0 de `status`, `next_min` sur l'octet 8.
