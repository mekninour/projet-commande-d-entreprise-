# Réglages du moteur d'alerte

Le client a demandé que **tous les réglages soient modifiables sans toucher au code** : OPALimpact choisira lui-même les bonnes valeurs. Les valeurs ci-dessous sont des **valeurs par défaut**, justifiées mais non validées par un hydrologue.

## Où les modifier

| Fichier | Portée |
|---|---|
| `parametres_alerte.json` | tous les capteurs |
| `seuils.csv`, colonne du même nom | un seul capteur (remplace la valeur commune) |

Les deux fichiers sont **relus à chaque mesure** : une modification s'applique sans redémarrer le moteur. Une valeur illisible est ignorée et signalée dans le journal du moteur (`[CONFIG] ...`). Si `parametres_alerte.json` manque, le moteur garde les valeurs par défaut du code.

Exemple : capteur 2 avec une montée rapide à 50 mm/h, les autres avec la valeur commune.
```csv
node_id,site,seuil_alerte,montee_rapide_mm_h
1,ST-VIG-01,300,
2,ST-VIG-02,300,50
```

## Les réglages

| Réglage | Défaut | Unité | Effet | Pourquoi cette valeur |
|---|---|---|---|---|
| `seuil_alerte` (seuils.csv seulement) | selon le site | mm | hauteur d'alerte du capteur | à fixer par site (référence Vigicrues) |
| `persistance_mesures` | 2 | mesures | nombre de mesures consécutives au-dessus du seuil avant l'alerte (filtre une mesure isolée) | le Livrable 1 propose 3 ; 2 garde l'alerte plus réactive avec une trame toutes les 15 min |
| `hysteresis_pct` | 10 | % | une fois en alerte, on n'en sort que sous seuil × (1 − 10 %) : évite le clignotement autour du seuil | Livrable 1 |
| `montee_rapide_mm_h` | 200 | mm/h | au-dessus du seuil, alerte immédiate (sans attendre la persistance) si l'eau monte au moins aussi vite. 0 = désactivé | calibrée sur 5 crues Vigicrues : au-dessus du bruit du capteur, détecte toutes les montées observées (voir AL4) |
| `temps_avant_seuil_min` | 15 | min | sous le seuil, alerte anticipée si, au rythme actuel, le seuil sera atteint dans ce délai. 0 = désactivé | une trame toutes les 15 min en vigilance (stratégie S4) |
| `saut_max_mm` | 1500 | mm | un écart plus grand entre deux mesures est jugé impossible (valeur aberrante) : il ne compte ni pour la vitesse ni pour l'anticipation. 0 = désactivé | 4 sauts aberrants de plus de 1,5 m observés sur la station 4 |
| `muet_facteur_next_min` | 2 | trames | capteur muet si aucune trame depuis `muet_facteur_next_min` × `next_min` + `muet_marge_min` | tolère une trame perdue isolée sans fausse alarme |
| `muet_marge_min` | 5 | min | marge ajoutée à l'échéance (retard réseau, horloge du nœud) | même règle que le tableau de bord (2 × `next_min` + 5 min) |
| `muet_next_min_defaut` | 30 | min | `next_min` utilisé quand la trame ne le donne pas (0xFF) | période fixe de la V1 |
| `muet_controle_s` | 60 | s | intervalle entre deux contrôles des échéances (réglage commun seulement, minimum 5 s) | une alerte « muet » au plus 1 min après l'échéance |

La cause publiée dans l'objet d'alerte (`cause`) vaut `seuil` ou `montee_rapide`.

## Capteur muet

Le moteur garde pour chaque capteur l'heure de sa dernière trame (valide ou non) et son `next_min`. Toutes les `muet_controle_s` secondes, il compare l'heure actuelle à l'échéance : dernière trame + 2 × `next_min` + 5 min (avec les réglages par défaut).

- **Échéance dépassée** : un objet AL3 est publié **une seule fois** sur `pce92/alertes/<node_id>`, avec `etat: "muet"`, `cause: "capteur_muet"`, le dernier niveau valide connu dans `hauteur_mm`, et l'heure de la dernière trame dans `received_at`.
- **Le capteur émet de nouveau** : un objet AL3 est publié **une seule fois**, avec `cause: "retour_capteur"` et `etat` = l'état du moteur avant le silence (`normal` ou `alerte`). L'objet habituel de la mesure suit aussitôt (si la mesure est valide).
- **Au démarrage**, le moteur relit dans la base la dernière trame de chaque capteur : un capteur déjà muet avant le redémarrage est signalé au premier contrôle.

L'heure de la dernière trame est l'heure d'arrivée dans le moteur (comme pour le tableau de bord), pas le `received_at` de la trame : l'injecteur, qui rejoue des trames avec une heure passée, ne déclenche donc pas de fausse alerte.

## Au démarrage du moteur

Pour retrouver son état (alerte en cours, compteur de persistance), le moteur **rejoue les 50 dernières mesures valides** du capteur dans la base, avec les réglages actuels. Il ne lit pas la colonne `alert` de la base : c'est le bit envoyé par le nœud (son propre seuil), pas l'état du moteur.

## Vérifier

```bash
python3 plateforme/config/test_parametres.py
python3 plateforme/config/test_capteurs_muets.py
```
Teste chaque réglage et la détection des capteurs muets, sans broker MQTT.

## Ce qui n'est pas ici

- **Réglages du capteur** (cadence de mesure et d'envoi, seuil du capteur) : dans le firmware du nœud (`emulateur/include/modes.h` pour l'émulateur), réglables par USB.
