# Émulateur de nœud ESP32

**Binôme :** B3 Émulateur & campagnes (Brahima Diarrassouba, Mathéo Vignaud)

Programme qui se fait passer pour le nœud capteur de Brest : il rejoue des séries réelles de hauteur d'eau (E3, E4), décide quand mesurer et quand émettre selon quatre modes (E5 : naïf, fréquence fixe, S4 fidèle au L1, S4 v1 simplifié), construit la trame de 12 octets du contrat d'interface v1.2 (E1) et compte les envois (E6).

**État (22/11/2026) :** tout fonctionne sur ordinateur (banc PC). Le portage sur la carte ESP32 avec la radio (E2) reste à faire.

## Contenu

```
emulateur/
├── Makefile                 # compile le banc PC et le test des modes
├── include/
│   ├── mesure.h             # struct Mesure, commune à toute la chaîne
│   ├── modes.h              # E5 : paramètres et état des 3 modes
│   ├── compteurs.h          # E6 : trames, octets, temps d'air, retard d'alerte
│   └── secrets.example.h    # modèle des clés radio (copier en secrets.h, jamais commité)
├── src/
│   └── modes.cpp            # E5 : la seule implémentation des modes (référence)
├── test/
│   ├── banc_pc.cpp          # banc : rejeu -> modes -> encodeur -> compteurs -> CSV
│   ├── lancer_campagne.sh   # 4 modes x tous les scénarios -> resultats/
│   └── test_modes.cpp       # essai rapide d'un mode sur un scénario
├── resultats/               # campagnes de référence (CSV)
└── proto/                   # prototypes Python : rejeu (E4), compteurs, R3
```

Les scénarios sont dans [`../donnees/scenarios/`](../donnees/README.md) (format `t_s;date_utc;hauteur_mm`).
L'encodeur de trame est dans [`../## Utilisation (depuis `emulateur/`)

```bash
make                     # compile ./banc et ./test_modes
make test                # vérifie la trame de test du contrat v1.2 (section 8)
make campagne            # 4 modes x tous les scénarios
make campagne ARGS="--reglage s4-regle"

./banc ../donnees/scenarios/scenario_03_Y346400501.csv tous --entete
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4 --hex     # trames et état veille/vigilance/alerte
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4v1 --reglage s4-regle
```

Options du banc : `--sf N` (défaut 10), `--radio lorawan|p2p` (en-tête de 13 ou 0 octet pour le temps d'air), `--reglage defaut|s4-regle|r3` (mode s4v1), `--periode-fixe S`, `--s4-delta MM`, `--s4-calme S`, `--s4-alerte S`, `--seuil MM` (seuil d'alerte absolu ; par défaut, niveau de base + 500 mm), `--regroupement` (voir plus bas).

## Les modes

| Mode | Mesure | Trame | Référence |
|---|---|---|---|
| `naif` | toutes les 5 min | à chaque mesure | S0b du L1 |
| `fixe` | toutes les 30 min | à chaque mesure | S0 du L1, rythme du contrat |
| `s4` | 15 min en veille, 5 min en vigilance et en alerte | veille : 1 / h ; vigilance et alerte : 1 / 15 min ; alerte : immédiate, bit 0 | **S4 du L1 (§3.4)** |
| `s4v1` | toutes les 5 min | calme / alerte + variation (réglages ci-dessous) | première version, chiffres du 16/11 |

**Mode `s4` (fidèle au L1) :**

| État | Entrée | Mesure | Trame |
|---|---|---|---|
| Veille | situation normale | 1 / 15 min | 1 / h (avec les 3 mesures précédentes si `--regroupement`) |
| Vigilance | niveau ≥ seuil bas, ou montée ≥ 20 cm/h entre 2 mesures | 1 / 5 min | 1 / 15 min |
| Alerte | niveau ≥ seuil d'alerte | 1 / 5 min | immédiate, puis 1 / 15 min, bit 0 levé ; fin d'alerte envoyée tout de suite |

- Seuil d'alerte : niveau de base + 500 mm (ou `--seuil`). Seuil bas : seuil d'alerte − 250 mm (hypothèse, le L1 ne le chiffre pas). Montée rapide : 20 cm/h (proposition AL4). Hystérésis : 50 mm.
- Valeur aberrante (saut de plus de 1,5 m entre deux mesures) ignorée, comme le ferait la médiane de 5 tirs du capteur.
- Capteur muet : une trame « mesure invalide » (0xFFFF) après 30 min sans mesure valide.
- Non codés : mode éco et défaut capteur (bits 1 à 7 de `status` interdits par le contrat v1.2).
- `--regroupement` : écrit dans les octets réservés 9 à 11 les écarts (cm signés, −128 = absente) entre les 3 mesures précédentes et la mesure envoyée. Proposition du L1, **hors contrat v1.2** (octets émis à 0x00) : le décodeur l'ignore ; à n'activer qu'avec l'accord de Brest (v1.3). Le nombre de trames ne change pas.

**Réglages du mode `s4v1` (`--reglage`) :**

| Réglage | Calme | Alerte | Variation qui déclenche un envoi |
|---|---|---|---|
| `defaut` | 1 h | 15 min | 50 mm |
| `s4-regle` (présenté au client le 16/11) | 2 h | 30 min | 100 mm |
| `r3` (hypothèses de la simulation R3 de Gaetan, alerte ramenée à 15 min) | 1 h | 15 min | 100 mm |

`modes.cpp` est la seule implémentation de référence : les prototypes Python doivent s'aligner sur ses règles. Deux étapes, comme dans la simulation R3 : `decider_emission()` dit s'il faut émettre, `confirmer_envoi()` mémorise un envoi réellement parti ; `doit_emettre()` enchaîne les deux.

## Format de l'export (E6)

`timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s,mesures`

`eveil_ms` vaut 0 sur ordinateur (mesuré avec `millis()` sur l'ESP32 seulement). `retard_alerte_s` est vide si le seuil n'est jamais franchi. `mesures` = mesures réellement prises par le capteur (coût énergétique du L1 : 0,0136 mAh par mesure).

vide si le seuil n'est jamais franchi.

## Reste à faire

- E2 : pile radio sur ESP32 (RadioLib), selon le choix LoRaWAN ou point à point.
- Regroupement : à valider avec Brest (octets réservés, v1.3) avant de l'activer par défaut.
- Mode éco et défaut capteur : demandent des bits de `status`, donc une évolution du contrat.
