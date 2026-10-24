# Mesure du gain : protocole, campagnes, analyse

Banc de test qui compare les modes d'émission (naïf, fréquence fixe, S4 hybride) et mesure le gain par rapport au modèle du L1.

Structure proposée :

```
mesures/
├── protocole.md    # M1 : métriques, scénarios, SF, durée
├── campagnes/      # M2 : données brutes (une campagne = un dossier daté, jamais modifié après coup)
├── analyse/        # M3, M4 : scripts, graphes, tableau comparatif
└── consommation/   # M5 (option) : mesures de courant
```

Règle : les données brutes ne sont **jamais retouchées** ; toute correction se fait dans les scripts d'analyse.

## Tâches du L2

| ID | Tâche | Critère de fin | Responsable | Dépend de | Période |
|---|---|---|---|---|---|
| M1 | Protocole du banc de test | Métriques, scénarios, SF, durée ; validé par l'équipe | Sasha Le Roux | — | Socle |
| M2 | Campagnes de mesure | 3 modes × 4–5 scénarios, données brutes archivées | Brahima Diarrassouba + Mohamed Amine Dahbi | M1, E6, S4 | Après |
| M3 | Analyse des résultats | Graphes, tableau comparatif, écart au modèle L1 | Sasha Le Roux | M2 | Après |
| M4 | Fréquence fixe contre S4 | Comparaison et recommandation argumentée | Sasha Le Roux | M3 | Après |
| M5 | Mesure de consommation réelle | Courant ESP32 (multimètre ou INA219) | Nour Mekni | E5 | Après |

État à jour : voir les issues GitHub correspondantes.
