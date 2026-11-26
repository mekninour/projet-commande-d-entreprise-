# Tableaux de bord (AL5, AL6)

**Binôme :** B1 – Nour Mekni

Les deux vues, faites avec **Node-RED Dashboard 2.0** (`@flowfuse/node-red-dashboard`). Elles lisent en temps réel les mesures et les événements publiés par S2 (`pce92/mesures/+`, `pce92/evenements`) et l'état calculé par le moteur d'alerte de B2 (`pce92/alertes/+`, programme `plateforme/config/moteur_alerte.py`).

| Vue | Adresse | Pour qui | Contenu |
|---|---|---|---|
| **AL5 – Vue simple** | `/dashboard/simple` | la mairie, sur téléphone | une carte par capteur, **triées du plus urgent au moins urgent** : l'**état** en couleur (NORMAL en vert, ALERTE en rouge, DONNÉES INDISPONIBLES en gris), la hauteur courante en cm, la tendance, le seuil d'alerte, la cause de l'alerte (seuil dépassé ou montée rapide) ou le temps avant dépassement s'il est proche (moins de 2 h), l'action à mener, l'heure de la dernière trame |
| **Historique** | `/dashboard/historique` | l'équipe, la mairie | on choisit un capteur et une période (24 h, 48 h, 7 jours, 30 jours) : la courbe du niveau avec le seuil actuel, un résumé (mesures reçues, trames perdues, taux de réception, mesures invalides, niveau maximal, mesures au-dessus du seuil), les événements de la période, et un lien d'export CSV |
| **AL6 – Vue technique** | `/dashboard/technique` | l'équipe, l'expert | **une tuile par capteur, triées du plus urgent au moins urgent** (alerte, données indisponibles, dépassement proche, normal), avec l'état, le niveau, la tendance, une mini-courbe avec le seuil (même axe de temps pour toutes les tuiles), les trames perdues et l'âge de la dernière trame ; en dessous, **les grandes courbes du capteur choisi** (niveau avec seuil, batterie) ; l'état de chaque capteur (état et d'où il vient, dernière trame, prochaine attendue, niveau, seuil, tendance et vitesse en mm/h, temps avant dépassement, bit d'alerte, batterie, signal, seq, trames perdues, taux de réception) ; l'état du récepteur ; les compteurs de trames perdues, doublons, rejets, retours de seq et trames reçues en retard ; les 10 derniers événements |

## Règles des courbes et des dates

- **Trames perdues** (seq qui saute) : la courbe est **coupée** à cet endroit. On ne trace pas de ligne entre deux mesures séparées par des trames jamais reçues, ce qui reviendrait à inventer des valeurs.
- **Mesure invalide** (0xFFFF) : même chose, la courbe du niveau est coupée à cet instant.
- **Capteur muet** : la courbe s'arrête à la dernière mesure.
- **Dates** : chaque mesure est datée à sa réception (règle 4 du contrat). Les heures sont envoyées en UTC et affichées dans le **fuseau de l'appareil qui consulte** : heure de Paris pour l'équipe, heure de Thiès sur place. Les textes et les courbes montrent donc toujours la même heure. L'axe des courbes indique le jour et l'heure (`12/11 08:30`), utile sur plusieurs jours.
- **Trames reçues en retard** (événement `trame_en_retard` de S2) : elles ne comptent plus comme perdues, mais elles ne sont pas tracées sur la courbe (leur heure de mesure n'est qu'estimée). Elles apparaissent dans les événements, avec leur mesure et l'heure estimée sur la page Historique.
- **Taux de réception** par capteur = trames reçues (y compris en retard) / (reçues + perdues).
- **Fenêtres de temps** : les courbes de la vue technique montrent les **48 dernières heures** (les points plus anciens sortent seuls de la courbe, rien n'est effacé de la base) ; les compteurs et les événements portent sur les **7 derniers jours** (rechargés depuis la base au démarrage). Pour remonter plus loin : la page **Historique**.

## Vue technique : quel capteur dans les grandes courbes ?

Les grandes courbes montrent **un capteur à la fois**, pour rester lisibles ; la comparaison entre capteurs se fait avec les tuiles et le tableau.

1. Sans action de l'expert : le capteur **le plus urgent** (la première tuile).
2. **Clic sur une tuile** : ce capteur, et ce choix est gardé.
3. Un capteur qui **entre en alerte** remplace ce choix : les courbes basculent sur lui, pour que l'urgence ne passe jamais inaperçue.

Au changement de capteur, ses 48 dernières heures sont relues dans la base (S3). Le choix est commun à tous les écrans ouverts sur le tableau de bord (limite du MVP).

Principes suivis : vue d'ensemble d'abord puis détail à la demande ; petites courbes répétées sur le même axe de temps ; tri par gravité ; couleur réservée à l'anormal et toujours doublée d'un mot (ALERTE, NORMAL, INDISPONIBLE) ; âge des données toujours visible.

## Page Historique

Elle relit la base de S3 **à la demande**, sans toucher à la vue en direct. Elle nécessite donc que le flux S3 (`plateforme/flows/s3_stockage.json`) soit importé : elle utilise sa base « pce92.db ».

- La liste des capteurs vient de la base (tous ceux qui ont au moins une mesure), avec le nom du site donné par le moteur.
- La courbe est coupée avant des trames perdues, sur une mesure invalide, et quand le capteur est resté muet plus de 2 × `next_min` + 5 min.
- Le seuil tracé est le **seuil actuel** (celui de `seuils.csv` connu du moteur), pas celui en vigueur à l'époque : l'historique des seuils et des états d'alerte n'est pas encore enregistré.
- « Exporter en CSV » télécharge les mesures de la même période par l'API de S3 (`/pce92/mesures?node_id=…&jours=…&format=csv`).

## D'où vient l'état

1. **Le moteur d'alerte de B2 décide.** À chaque mesure valide, il lit le seuil du capteur dans `plateforme/config/seuils.csv` et publie sur `pce92/alertes/<node_id>` un objet `{ node_id, site, etat, cause, hauteur_mm, seuil_mm, tendance, vitesse_mm_h, temps_avant_depassement_min, received_at }`. Les vues affichent cet état tel quel : le moteur gère la montée rapide et la marge de retour (l'alerte ne s'arrête pas dès que le niveau repasse juste sous le seuil, pour ne pas clignoter). Le nom du site vient aussi de `seuils.csv`.
2. **Calcul de secours** : tant que le moteur n'a rien publié pour un capteur (moteur arrêté), les vues comparent la hauteur à un seuil de secours de 300 mm, et passent en ALERTE si le nœud a levé son bit d'alerte (règle 3 du contrat v1.2). La vue technique l'indique (« calcul de secours (moteur absent) »).
3. **Sans mesure exploitable** (aucune nouvelle trame depuis 2 × `next_min` + 5 min, ou mesure invalide 0xFFFF), on affiche **DONNÉES INDISPONIBLES** en gris : on ne peut pas juger, donc **jamais de NORMAL**. La carte indique le dernier niveau connu et l'heure de cette mesure. Ce contrôle est fait par les vues, car la détection du capteur muet n'est pas encore active dans le moteur.

**Modifier un seuil sans toucher au code** : changer la valeur dans `plateforme/config/seuils.csv` et enregistrer. Le moteur relit le fichier à chaque mesure : la mesure suivante utilise le nouveau seuil, et la ligne de seuil de la courbe change de niveau à cet instant.

## Réglages

En tête du nœud *Préparer l'affichage* :

| Réglage | Valeur | Origine |
|---|---|---|
| Seuil de secours | 300 mm | repère de danger du contrat v1.2 ; utilisé seulement si le moteur est arrêté |
| Annonce du dépassement (vue simple) | si prévu dans moins de 2 h | au-delà, le chiffre n'a pas de sens pour la mairie |
| Actions par état | NORMAL : aucune action ; ALERTE : prévenir les zones à risque et se préparer à évacuer | à faire valider par le client |
| Batterie faible | sous 3,20 V | contrat v1.2 (périmètre V2) |

## Limites

- **Rechargement au démarrage** : si le flux S3 est importé, les mesures **et** les événements des 7 derniers jours sont rechargés depuis la base au démarrage de Node-RED (courbes sur 48 h, compteurs, taux de réception). Sans S3, la vue en direct repart de zéro au redémarrage, et la page Historique ne fonctionne pas.
- **Réinitialiser l'affichage** (dans l'éditeur) n'efface que l'écran, pas la base. C'est un outil de test : sur le terrain, on ne l'utilise pas.
- Les courbes relient les points dans leur ordre d'arrivée. Si l'on rejoue deux scénarios sur le même capteur, leurs heures simulées se chevauchent. Pour l'éviter, utiliser un `--node-id` différent par scénario, ou cliquer sur *Réinitialiser l'affichage* dans l'éditeur.

## Installation

Prérequis : le flux **S2** (`plateforme/flows/s2_reception.json`) est déjà importé (ce flux réutilise son serveur MQTT « Mosquitto local »), et le module `@flowfuse/node-red-dashboard` est installé (menu ☰ → *Manage palette*).

1. Menu ☰ → *Import* → `plateforme/dashboards/dashboard_mvp.json` → *Import* → **Deploy**. Si l'ancienne version est déjà importée, Node-RED propose de **remplacer** les nœuds existants : accepter.
2. Ouvrir http://localhost:1880/dashboard. Le menu ☰ en haut à gauche passe d'une vue à l'autre.
3. Lancer le moteur d'alerte, **depuis la racine du dépôt** (il cherche `plateforme/config/seuils.csv` à partir de là) :
   ```
   py -m pip install paho-mqtt
   py plateforme\config\moteur_alerte.py
   ```
   Il affiche « Abonné à pce92/mesures/+ ». Laisser la fenêtre ouverte.
4. Envoyer des mesures avec l'injecteur, par exemple `py injecteur.py --scenario montee --node-id 3`. Le `--node-id` doit figurer dans `seuils.csv` (1, 2 ou 3), sinon le moteur ne publie rien pour ce capteur.

Depuis un téléphone connecté au même Wi-Fi : `http://<adresse IP du PC>:1880/dashboard/simple`. L'adresse IP s'obtient avec `ipconfig`.

## Démonstration (environ 1 min)

1. Dans l'éditeur, onglet *AL5 / AL6*, cliquer sur le bouton du nœud **Réinitialiser l'affichage**.
2. Lancer `py injecteur.py --scenario montee --node-id 3`.
3. Vue simple : NORMAL, puis « seuil atteint dans … environ » quand le niveau approche, ALERTE au-dessus de 300 mm, et retour au NORMAL seulement quand le niveau a vraiment baissé.
4. Vue technique : la courbe franchit la ligne du seuil puis redescend ; le tableau montre la tendance, la vitesse et la source de l'état (« moteur d'alerte »).
5. Pour montrer le réglage du seuil : relancer le scénario, et pendant la montée changer `300` en `250` pour le capteur 3 dans `seuils.csv`, puis enregistrer. La ligne de seuil descend à 250 mm et l'alerte arrive plus tôt.
