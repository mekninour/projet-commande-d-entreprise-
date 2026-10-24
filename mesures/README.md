# Mesure du gain : protocole, campagnes, analyse

**Binôme :** B2 (protocole, analyse), B3 (campagnes), B1 (consommation)

Banc de test qui compare les modes d'émission (naïf, fréquence fixe, S4 hybride) et mesure le gain par rapport au modèle du L1.

Structure proposée :

```
mesures/
├── protocole.md    # métriques, scénarios, SF, durée
├── campagnes/      # données brutes (une campagne = un dossier daté, jamais modifié après coup)
├── analyse/        # scripts, graphes, tableau comparatif
└── consommation/   # mesures de courant
```

Règle : les données brutes ne sont **jamais retouchées** ; toute correction se fait dans les scripts d'analyse.
