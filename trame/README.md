# Trame de 12 octets : encodeur, décodeur, exemples

**Binôme :** B2 (encodeur) et B1 (décodeur)

Ce dossier est **l'interface entre les binômes** et avec Brest. Il contient la seule définition de la trame dans le code, conforme au [contrat d'interface](../docs/contrat_interface.md).

Structure proposée :

```
trame/
├── encodeur/       # encodage C/C++ (réutilisé par l'émulateur), tests unitaires
├── decodeur/       # codec JavaScript pour ChirpStack, tests
└── exemples/       # trames de référence partagées (CSV) : chaque encodeur et décodeur doit les passer
```

Règle : **toute nouvelle trame de test va dans `exemples/exemples_trames.csv`**, et les tests de l'encodeur et du décodeur la relisent. Ainsi l'encodeur et le décodeur ne peuvent pas diverger.

Hypothèse de travail (non validée par Brest ni le client) : `batt_cv` à 20 mV par unité. Le bit d'alerte de `status` est le MSB (décision de la réunion Brest–Rennes du 16/10, à faire confirmer par écrit par Brest).
