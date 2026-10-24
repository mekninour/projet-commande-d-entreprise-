# Outils du projet

## Créer les issues de suivi du L2

`creer_issues.py` lit `taches_L2.csv` (les 49 tâches du tableur de répartition) et crée sur GitHub :

- 18 labels : lots (`lot:E`…), binômes (`B1`, `B2`, `B3`, `transverse`), période (`socle`, `stretch`, `apres`), `bloque`, `option` ;
- le jalon `L2` ;
- une issue par tâche, titrée `[ID] Intitulé`, avec le critère de fin, les dépendances, la charge et les labels. Les tâches au statut « Fait » sont fermées aussitôt.

Étapes :

1. Installer GitHub CLI (`brew install gh` sur Mac) puis `gh auth login`.
2. Renseigner les logins GitHub dans `membres.csv` (une colonne vide = pas d'assignation).
3. Depuis la racine du dépôt : `python3 outils/creer_issues.py --essai` pour vérifier, puis `python3 outils/creer_issues.py`.
4. Dans l'onglet *Projects* du dépôt, créer un tableau (modèle *Board*) et y ajouter les issues du jalon `L2`. Colonnes : À faire, En cours, En relecture, Fait.

Le script peut être relancé sans créer de doublons. `taches_L2.csv` est une copie du tableur au 16/10/2026 : après création, **les issues font foi** pour le statut.
