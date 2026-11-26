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

La cause publiée dans l'objet d'alerte (`cause`) vaut `seuil` ou `montee_rapide`.

## Vérifier

```bash
python3 plateforme/config/test_parametres.py
```
Teste chaque réglage sans broker MQTT.

## Ce qui n'est pas ici

- **Capteur muet** : détecté par le tableau de bord (aucune trame depuis 2 × `next_min` + 5 min), pas par le moteur.
- **Réglages du capteur** (cadence de mesure et d'envoi, seuil du capteur) : dans le firmware du nœud (`emulateur/include/modes.h` pour l'émulateur), réglables par USB.
