#!/bin/sh
# 3 modes x tous les scénarios de donnees/scenarios -> resultats/campagne_<date>.csv
# Options passées au banc (ex. : ./test/lancer_campagne.sh --radio p2p)
cd "$(dirname "$0")/.." || exit 1
mkdir -p resultats
sortie="resultats/campagne_$(date +%Y%m%d_%H%M%S).csv"
echo "timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s" > "$sortie"
for f in ../donnees/scenarios/*.csv; do
    ./banc "$f" tous "$@" >> "$sortie" || exit 1
done
echo "Résultats : emulateur/$sortie"
cat "$sortie"
