# Scénarios de crue (Vigicrues)

Séries de hauteur d'eau réelles, nettoyées, qui alimentent l'émulateur (E4) et les tests d'alerte (AL7).

Structure proposée :

```
donnees/
├── brutes/         # fichiers téléchargés tels quels (source et date dans FORMAT.md)
├── scenarios/      # 4 à 5 scénarios nettoyés : nominal, montée rapide, crue extrême, panne réseau
└── FORMAT.md       # format des fichiers (colonnes, unités, pas de temps)
```

Les scénarios suivent la section 6 du contrat d'interface.

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| E3 | Jeux de données Vigicrues | 4–5 scénarios nettoyés, format documenté | Brahima Diarrassouba | P2f | Socle |

État à jour : voir les issues GitHub correspondantes.
