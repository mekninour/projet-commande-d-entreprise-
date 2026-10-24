# Conventions de travail

Des règles courtes, pour que les 6 membres travaillent sur le même dépôt sans se gêner. Elles sont modifiables : proposez un changement en réunion du lundi.

## 1. Les tâches

- **Une tâche du L2 = une issue**, titrée par son identifiant : `[E4] Rejeu des séries`. Le corps reprend le critère de fin, les dépendances et le responsable.
- Labels : le **lot** (`lot:E`), le **binôme** (`B3`), la **période** (`socle`, `stretch`, `apres`) et, si besoin, `bloque` ou `option`.
- L'état se lit sur le tableau GitHub Projects : *À faire → En cours → En relecture → Fait*. Une issue fermée = tâche terminée (critère de fin atteint).
- Une tâche bloquée : label `bloque` + un commentaire qui dit par quoi (ex. « attend la livraison du RAK5146 »).

## 2. Les branches

- `main` contient toujours une version qui fonctionne. **On ne pousse jamais directement sur `main`.**
- Une branche par tâche (ou par étape d'une grosse tâche), nommée `<ID>-<description-courte>` :

```
E4-rejeu-series
AL2-moteur-alerte
A4-chirpstack-docker
```

## 3. Les commits

Format : `[ID] Verbe à l'infinitif + ce qui change`, en français.

```
[E1] Ajouter l'encodeur de trame et le test de l'exemple officiel
[S5] Corriger le format du topic MQTT de l'injecteur
[docs] Mettre à jour le contrat d'interface (bit d'alerte)
```

Des petits commits fréquents valent mieux qu'un gros commit en fin de semaine.

## 4. Les pull requests

- Une PR par branche, avec `Closes #<numéro de l'issue>` dans la description si elle termine la tâche.
- **Relecture par 1 autre membre** avant fusion, de préférence celui qui utilise le résultat (ex. l'encodeur E1 relu par B3, qui l'intègre dans l'émulateur).
- Fusion par l'auteur, une fois la PR approuvée.

## 5. Ce qui ne va jamais dans le dépôt

| Interdit | À la place |
|---|---|
| Clés LoRaWAN (DevEUI, AppKey, NwkKey), mots de passe, jetons d'API | `secrets.h` ou `.env`, ignorés par Git ; un modèle `secrets.example.h` ou `.env.example` est commité |
| Identifiants Node-RED (`flows_cred.json`) | Ignorés par Git |
| Fichiers de plus de 50 Mo, vidéos, binaires compilés | Google Drive, avec un lien dans le README du dossier |
| Livrables, comptes rendus, slides | Google Drive de l'équipe |

Une clé commitée par erreur doit être **régénérée dans ChirpStack** : la supprimer du dépôt ne suffit pas, elle reste dans l'historique.

## 6. Langue et nommage

- Documentation, commentaires, commits et issues : **français**.
- Noms dans le code : anglais court, alignés sur le contrat (`node_id`, `water_mm`, `batt_cv`, `seq`, `status`).
- Noms propres : LoRaWAN, ChirpStack, Node-RED, OPALimpact, Raspberry Pi.

## 7. Données

- Données brutes (campagnes, séries Vigicrues) : en CSV, dans un dossier daté, **jamais retouchées après coup**.
- Toute correction ou tout filtrage se fait dans un script d'analyse versionné.
- Chaque dossier de données a un `FORMAT.md` (colonnes, unités, source, date).
