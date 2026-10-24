# Conventions de travail

Des règles courtes, pour que les 6 membres travaillent sur le même dépôt sans se gêner. Elles sont modifiables : proposez un changement en réunion du lundi.

## 1. Les branches

- `main` contient toujours une version qui fonctionne. **On ne pousse jamais directement sur `main`.**
- Une branche par sujet, nommée `<dossier>-<description-courte>` :

```
emulateur-rejeu-series
trame-decodeur
passerelle-chirpstack-docker
```

Le suivi des tâches (qui fait quoi, état d'avancement) reste dans le tableur de répartition, sur le Drive.

## 2. Les commits

Format : `[dossier] Verbe à l'infinitif + ce qui change`, en français.

```
[trame] Ajouter l'encodeur et le test de l'exemple officiel
[plateforme] Corriger le format du topic MQTT de l'injecteur
[docs] Mettre à jour le contrat d'interface (bit d'alerte)
```

Des petits commits fréquents valent mieux qu'un gros commit en fin de semaine.

## 3. Les pull requests

- Une PR par branche.
- **Relecture par 1 autre membre** avant fusion, de préférence celui qui utilise le résultat (ex. l'encodeur de trame relu par B3, qui l'intègre dans l'émulateur).
- Fusion par l'auteur, une fois la PR approuvée.

## 4. Ce qui ne va jamais dans le dépôt

| Interdit | À la place |
|---|---|
| Clés LoRaWAN (DevEUI, AppKey, NwkKey), mots de passe, jetons d'API | `secrets.h` ou `.env`, ignorés par Git ; un modèle `secrets.example.h` ou `.env.example` est commité |
| Identifiants Node-RED (`flows_cred.json`) | Ignorés par Git |
| Fichiers de plus de 50 Mo, vidéos, binaires compilés | Google Drive, avec un lien dans le README du dossier |
| Livrables, comptes rendus, slides | Google Drive de l'équipe |

Une clé commitée par erreur doit être **régénérée dans ChirpStack** : la supprimer du dépôt ne suffit pas, elle reste dans l'historique.

## 5. Langue et nommage

- Documentation, commentaires et commits : **français**.
- Noms dans le code : anglais court, alignés sur le contrat (`node_id`, `water_mm`, `batt_cv`, `seq`, `status`).
- Noms propres : LoRaWAN, ChirpStack, Node-RED, OPALimpact, Raspberry Pi.

## 6. Données

- Données brutes (campagnes, séries Vigicrues) : en CSV, dans un dossier daté, **jamais retouchées après coup**.
- Toute correction ou tout filtrage se fait dans un script d'analyse versionné.
- Chaque dossier de données a un `FORMAT.md` (colonnes, unités, source, date).
