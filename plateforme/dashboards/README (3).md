# Tableaux de bord (AL5, AL6)

**Binôme :** B1 – Nour Mekni

Les deux vues, faites avec **Node-RED Dashboard 2.0** (`@flowfuse/node-red-dashboard`). Elles lisent en temps réel les mesures et les événements publiés par S2 (`pce92/mesures/+`, `pce92/evenements`) et, quand il sera prêt, le palier calculé par le moteur d'alerte de B2 (`pce92/alertes/+`).

| Vue | Adresse | Pour qui | Contenu |
|---|---|---|---|
| **AL5 – Vue simple** | `/dashboard/simple` | la mairie, sur téléphone | une carte par capteur : le **palier** en couleur (vert, jaune, orange, rouge), l'échelle des 4 paliers avec le palier courant en surbrillance, la hauteur courante en cm, la tendance, l'action à mener, l'heure de la dernière trame |
| **AL6 – Vue technique** | `/dashboard/technique` | l'équipe, l'expert | la courbe de la hauteur dans le temps avec les seuils des paliers ; la courbe de la batterie ; l'état de chaque capteur (palier, dernière trame, prochaine attendue, bit d'alerte, batterie, signal, seq) ; l'état du récepteur ; les compteurs de trames perdues, doublons et rejets ; les 10 derniers événements |

## D'où vient le palier

1. **Si le moteur d'alerte de B2 (AL2) a publié un palier** pour ce capteur, on affiche celui-là. C'est lui qui applique la persistance, la montée rapide et la marge de retour (L1, partie 4.1.3).
2. **Sinon (calcul provisoire)** : on compare la dernière hauteur valide aux seuils du site, puis on passe en **rouge** si le nœud a levé son bit d'alerte (règle 3 du contrat v1.2).
3. **Sans mesure exploitable** (aucune nouvelle trame arrivée depuis `next_min` + une marge de la moitié de `next_min`, au moins 5 min ; ou mesure invalide 0xFFFF), on affiche **DONNÉES INDISPONIBLES** en gris. Ce n'est pas un palier : on ne peut pas juger, donc on n'affiche **jamais de vert** (L1, partie 4.2.1). La carte indique alors le dernier niveau connu et l'heure de cette mesure.

La vue technique précise, pour chaque capteur, si le palier vient du moteur d'alerte ou du calcul provisoire.

**Format proposé à B2 pour le moteur d'alerte** : un message sur le topic `pce92/alertes/<node_id>`, contenant au minimum `{ "node_id": 3, "palier": "vert" | "jaune" | "orange" | "rouge" }`.

## Réglages provisoires

Ils se trouvent en tête du nœud *Préparer l'affichage*, en attendant le fichier de seuils et de sites de B2 (AL1) :

| Réglage | Valeur | Origine |
|---|---|---|
| Seuil jaune | 100 mm | marge critique du contrat v1.2 |
| Seuil orange | 200 mm | **provisoire**, valeur intermédiaire |
| Seuil rouge | 300 mm | repère de danger du contrat v1.2 (Géorisques) |
| Noms des sites | « Site de test (nœud 3) » | à remplacer |
| Actions par palier | reprises du L1 (4.1.2) | à faire valider par le client |
| Batterie faible | sous 3,20 V | contrat v1.2 (périmètre V2) |

Les seuils peuvent être réglés capteur par capteur avec `SEUILS_PAR_SITE`.

## Limites

- **L'historique n'est pas encore durable** : les courbes gardent 7 jours en mémoire, mais s'effacent au redémarrage de Node-RED. Le stockage (S3) les rechargera depuis la base.
- Les courbes relient les points dans leur ordre d'arrivée. Si l'on rejoue deux scénarios sur le même capteur, leurs heures simulées se chevauchent. Pour l'éviter, utiliser un `--node-id` différent par scénario, ou cliquer sur *Réinitialiser l'affichage* dans l'éditeur.

## Installation

Prérequis : le flux **S2** (`plateforme/flows/s2_reception.json`) est déjà importé (ce flux réutilise son serveur MQTT « Mosquitto local »), et le module `@flowfuse/node-red-dashboard` est installé (menu ☰ → *Manage palette*).

1. Menu ☰ → *Import* → `plateforme/dashboards/dashboard_mvp.json` → *Import* → **Deploy**. Si l'ancienne version est déjà importée, Node-RED propose de **remplacer** les nœuds existants : accepter.
2. Ouvrir http://localhost:1880/dashboard. Le menu ☰ en haut à gauche passe d'une vue à l'autre.
3. Envoyer des mesures avec l'injecteur, par exemple `py injecteur.py --scenario montee`.

Depuis un téléphone connecté au même Wi-Fi : `http://<adresse IP du PC>:1880/dashboard/simple`. L'adresse IP s'obtient avec `ipconfig`.

## Démonstration (environ 1 min)

1. Dans l'éditeur, onglet *AL5 / AL6*, cliquer sur le bouton du nœud **Réinitialiser l'affichage**.
2. Lancer `py injecteur.py --scenario montee --node-id 3`.
3. Vue technique : la courbe franchit les seuils jaune, orange et rouge, puis redescend.
4. Vue simple : la carte passe du vert au jaune, à l'orange, puis au rouge, et redescend jusqu'au vert.
