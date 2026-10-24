# Alertes : seuils, moteur, objet d'alerte

Logique d'alerte définie dans l'annexe C du L1 : paliers, persistance, montée rapide, hystérésis, capteur muet.

Structure proposée :

```
alertes/
├── seuils/         # AL1 : un fichier de configuration par site, modifiable sans code
├── moteur/         # AL2, AL3 : moteur d'alerte et format JSON de l'objet d'alerte
├── tests/          # AL7 : scénarios rejoués et résultats archivés
└── export/         # G2 : format d'export vers OPAL
```

Périmètre (CR du 12/10, indicatif) : SMS, acquittement et escalade sont hors L2.

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| AL1 | Seuils par site | Fichier de config par site, modifiable sans code | Sasha Le Roux | — | Socle |
| AL2 | Moteur d'alerte | Paliers, persistance, montée rapide, hystérésis, capteur muet | Sasha Le Roux + Gaetan Boulard | AL1, S5 | Stretch |
| AL3 | Objet d'alerte | JSON : site, palier, hauteur, tendance, horodatage | Gaetan Boulard | AL2 | Après |
| AL4 | Calibrage montée rapide | Valeur validée avec le client | Sasha Le Roux | AL2, réponse client | Après |
| AL7 | Tests d'alerte | Scénarios rejoués dans le moteur, résultats archivés | Gaetan Boulard | AL2, E4 | Après |
| R6 | Seuils à distance | Principe de mise à jour des seuils (fenêtre classe A) | Gaetan Boulard | P4 | Stretch |
| G2 | Export OPAL | Format d'export de l'alerte | Gaetan Boulard | AL3 | Après |

État à jour : voir les issues GitHub correspondantes.
