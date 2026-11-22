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

./banc ../donnees/scenarios/scenario_03_Y346400501.csv tous --entete
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4 --reglage s4-regle
./banc ../donnees/scenarios/scenario_03_Y346400501.csv s4 --hex    # trames qui défilent
```

Options du banc : `--sf N` (défaut 10), `--radio lorawan|p2p` (en-tête de 13 ou 0 octet pour le temps d'air), `--reglage defaut|s4-regle`, `--periode-fixe S`, `--s4-delta MM`, `--s4-calme S`, `--s4-alerte S`, `--seuil MM` (seuil d'alerte absolu ; par défaut, niveau de base + 500 mm).

## Réglages des modes

| Mode | Réglage `defaut` | Réglage `s4-regle` (présenté au client le 16/11) |
|---|---|---|
| Naïf | 1 trame par mesure (5 min) | identique |
| Fixe | 1 trame / 30 min (référence du contrat) | identique |
| S4 | calme 1 h, alerte 15 min, envoi si l'eau varie de 50 mm | calme 2 h, alerte 30 min, envoi si l'eau varie de 100 mm |

Seuil d'alerte de S4 : niveau de base (plus basse hauteur vue) + 500 mm, avec 50 mm d'hystérésis, sauf si `--seuil` est donné.
`modes.cpp` est la seule implémentation de référence : les prototypes Python doivent s'aligner sur ses valeurs.

## Format de l'export (E6)

`timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s`

`eveil_ms` vaut 0 sur ordinateur (mesuré avec `millis()` sur l'ESP32 seulement). `retard_alerte_s` est vide si le seuil n'est jamais franchi.

## Reste à faire

- E2 : pile radio sur ESP32 (RadioLib), selon le choix LoRaWAN ou point à point.
- Regroupement de 4 mesures par trame (prévu au L1, pas encore codé).
