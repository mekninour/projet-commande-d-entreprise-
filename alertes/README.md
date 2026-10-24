# Alertes : seuils, moteur, objet d'alerte

**Binôme :** B2 Contrat, alertes & analyse

Logique d'alerte définie dans l'annexe C du L1 : paliers, persistance, montée rapide, hystérésis, capteur muet.

Structure proposée :

```
alertes/
├── seuils/         # un fichier de configuration par site, modifiable sans code
├── moteur/         # moteur d'alerte et format JSON de l'objet d'alerte
├── tests/          # scénarios rejoués et résultats archivés
└── export/         # format d'export vers OPAL
```

Périmètre (CR du 12/10, indicatif) : SMS, acquittement et escalade sont hors L2.
