# Émulateur de nœud ESP32

**Binôme :** B3 Émulateur & campagnes (Brahima Diarrassouba, Mathéo Vignaud)

Programme qui se fait passer pour le nœud capteur de Brest : il rejoue des séries réelles de hauteur d'eau (E3, E4), décide quand émettre selon trois modes (E5 : naïf, fréquence fixe, S4 hybride), construit la trame de 12 octets du contrat d'interface v1.2 (E1) et compte les envois (E6).

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
│   ├── lancer_campagne.sh   # 3 modes x tous les scénarios -> resultats/
│   └── test_modes.cpp       # essai rapide d'un mode sur un scénario
├── resultats/               # campagnes de référence (CSV)
└── proto/                   # prototypes Python : rejeu (E4), compteurs, R3
```

Les scénarios sont dans [`../donnees/scenarios/`](../donnees/README.md) (format `t_s;date_utc;hauteur_mm`).
L'encodeur de trame est dans [`../trame/encodeur/`](../trame/encodeur/).

## Utilisation (depuis `emulateur/`)

```bash
make                     # compile ./banc et ./test_modes
make test                # vérifie la trame de test du contrat v1.2 (section 8)
make campagne            # 3 modes x tous les scénarios, réglage par défaut
make campagne ARGS="--reglage s4-regle"
make campagne ARGS="--reglage r3"

./banc ../donnees/scenarios/scenario_03_Y346400501.csv tous --entete
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4 --reglage s4-regle
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4 --hex    # trames qui défilent
```

Options du banc : `--sf N` (défaut 10), `--radio lorawan|p2p` (en-tête de 13 ou 0 octet pour le temps d'air), `--reglage defaut|s4-regle|r3`, `--periode-fixe S`, `--s4-delta MM`, `--s4-calme S`, `--s4-alerte S`, `--seuil MM` (seuil d'alerte absolu ; par défaut, niveau de base + 500 mm).

## Réglages des modes

| Mode | `defaut` (L1) | `s4-regle` (présenté au client le 16/11) | `r3` (hypothèses de la simulation R3) |
|---|---|---|---|
| Naïf | 1 trame par mesure (5 min) | identique | identique |
| Fixe | 1 trame / 30 min (référence du contrat) | identique | identique |
| S4 | calme 1 h, alerte 15 min, variation 50 mm | calme 2 h, alerte 30 min, variation 100 mm | calme 1 h, alerte 10 min, variation 100 mm |

Le réglage `r3` donne exactement les mêmes nombres de trames que `emulateur/proto/sim_camarades.py` (branche R3) : les deux implémentations sont alignées.

Seuil d'alerte de S4 : niveau de base (plus basse hauteur vue) + 500 mm, avec 50 mm d'hystérésis, sauf si `--seuil` est donné.
`modes.cpp` est la seule implémentation de référence : les prototypes Python doivent s'aligner sur ses valeurs.

Deux étapes, comme dans la simulation R3 : `decider_emission()` dit s'il faut émettre, `confirmer_envoi()` mémorise un envoi réellement parti. `doit_emettre()` enchaîne les deux (envoi supposé réussi).

**S4 v1, simplifié par rapport au L1 (§3.4) :** 2 états (calme, alerte) au lieu de 3 (pas d'état vigilance), mesure toujours toutes les 5 min (pas de mesure toutes les 15 min au calme), 1 mesure par trame (pas de regroupement de 4 mesures), pas de mode éco ni de défaut capteur (bits interdits par le contrat v1.2).

## Format de l'export (E6)

`timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s`

`eveil_ms` vaut 0 sur ordinateur (mesuré avec `millis()` sur l'ESP32 seulement). `retard_alerte_s` est vide si le seuil n'est jamais franchi.

## Reste à faire

- E2 : pile radio sur ESP32 (RadioLib), selon le choix LoRaWAN ou point à point.
- Regroupement de 4 mesures par trame (prévu au L1, pas encore codé).
