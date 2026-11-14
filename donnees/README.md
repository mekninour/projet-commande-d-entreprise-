# E3 · Jeux de données Vigicrues — format des scénarios

## Format (figé, v1.0)

| Élément        | Valeur |
|----------------|--------|
| Fichier        | CSV, UTF-8, fins de ligne LF |
| Séparateur     | `;` |
| En-tête        | une ligne : `t_s;date_utc;hauteur_mm` |
| `t_s`          | secondes depuis le début du scénario, entier, commence à 0 |
| `date_utc`     | ISO 8601 UTC : `AAAA-MM-JJTHH:MM:SSZ` |
| `hauteur_mm`   | hauteur d'eau en mm, entier (0 à 65534) |
| Mesure invalide| `hauteur_mm = 65535` (= `MESURE_INVALIDE` 0xFFFF de `mesure.h`) |
| Pas de temps   | **5 min (300 s), régulier** : `t_s` augmente toujours de 300 |
| Nom            | `scenario_NN_<code_station>.csv` |
| Source         | Vigicrues (Hub'Eau / Hydroportail), grandeur H |

Exemple :

```
t_s;date_utc;hauteur_mm
0;2026-10-29T00:00:00Z;651
300;2026-10-29T00:05:00Z;647
```

## Règles de nettoyage

1. Tri chronologique, doublons supprimés (la dernière valeur est gardée).
2. Recalage sur une grille régulière de 5 min.
3. Trou de 30 min ou moins : interpolation linéaire.
4. Trou de plus de 30 min : lignes conservées avec `hauteur_mm = 65535` (invalide).
   La grille reste donc toujours régulière et le rejeu reçoit les trous.
5. Hauteur négative (sous le zéro de l'échelle) : ramenée à 0, car `uint16_t`.

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `scenario_00_SIMULE.csv` | crue simulée de 24 h, sans trou (test) |
| `scenario_00b_SIMULE_trous.csv` | même crue avec 1 petit trou interpolé et 16 mesures invalides (test) |
| `scenario_01..05_<station>.csv` | vrais épisodes de crue (à produire avec l'outil) |
| `preparer_scenarios.py` | outil de téléchargement, nettoyage et validation |

## Produire les 5 vrais scénarios (une commande)

Crues de début novembre 2026 (vigilance orange en Corse, Gard, Hérault).
Hub'Eau garde 30 jours : à lancer **avant début décembre 2026**.

```bash
pip install requests
python preparer_scenarios.py chercher 2A 2B 30 34 \
       --debut 2026-11-03T00:00 --fin 2026-11-09T00:00 --creer 5
```

L'outil parcourt les stations de ces départements, garde celles au pas de 5 min,
classe les plus fortes montées et écrit `scenario_01..05_<station>.csv`, validés.

## Autres commandes

```bash
pip install requests
# a) ~30 derniers jours depuis Hub'Eau
python preparer_scenarios.py hubeau J712001001
# b) ou un export d'une crue passée téléchargé sur Hydroportail (hauteurs instantanées)
python preparer_scenarios.py nettoyer brut.csv scenario_01_J712001001.csv \
       --debut 2026-01-10T00:00 --fin 2026-01-14T00:00 --unite mm
# c) vérification de tous les scénarios
python preparer_scenarios.py valider scenario_*.csv
```

Options de `nettoyer` : `--unite mm|cm|m` (unité du fichier brut),
`--heure-locale` si les dates du brut sont en heure française.
