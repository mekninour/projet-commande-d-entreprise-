# Trame de 12 octets : encodeur, décodeur, exemples

Ce dossier est **l'interface entre les binômes** et avec Brest. Il contient la seule définition de la trame dans le code, conforme au [contrat d'interface](../docs/contrat_interface.md).

Structure proposée :

```
trame/
├── encodeur/       # E1 : encodage C/C++ (réutilisé par l'émulateur), tests unitaires
├── decodeur/       # S1 : codec JavaScript pour ChirpStack, tests
└── exemples/       # trames de référence partagées (CSV) : chaque encodeur et décodeur doit les passer
```

Règle : **toute nouvelle trame de test va dans `exemples/exemples_trames.csv`**, et les tests de l'encodeur et du décodeur la relisent. Ainsi l'encodeur et le décodeur ne peuvent pas diverger.

Hypothèse de travail (non validée par Brest ni le client) : `batt_cv` à 20 mV par unité. Le bit d'alerte de `status` (MSB ou LSB) attend la réponse de Brest (P4).

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| E1 | Encodeur de trame | 12 octets conformes au contrat, tests unitaires (exemple du contrat) | Gaetan Boulard | P4 (partielle) | Socle |
| S1 | Décodeur ChirpStack | Codec JS des 12 octets (y c. agrégation S4), testé | Nour Mekni | E1 | Socle |
| G1 | Préparation intégration Brest | Interface prête pour le nœud réel | Gaetan Boulard | S4, P4 | Après |

État à jour : voir les issues GitHub correspondantes.
