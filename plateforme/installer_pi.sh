#!/usr/bin/env bash
# PCE 92 – Préparer la plateforme (Node-RED + moteur d'alerte) sur le Raspberry Pi.
#
# Lancer depuis n'importe où, sur le Pi, sans sudo :
#   bash plateforme/installer_pi.sh
#
# Le script ne touche ni à ChirpStack ni aux flux déjà présents dans Node-RED. Il :
#   1. vérifie que Node-RED est installé ;
#   2. installe les deux modules Node-RED nécessaires (tableaux de bord, SQLite) ;
#   3. indique à Node-RED où se trouve le décodeur (codec S1), dans settings.js ;
#   4. prépare UN fichier à importer dans Node-RED (S2 + S3 + tableaux de bord),
#      avec le chemin de la base adapté au Pi ;
#   5. prépare le moteur d'alerte (module paho-mqtt, accès à la base) ;
#   6. affiche les capteurs connus de seuils.csv ;
#   7. redémarre Node-RED et y déploie les flux PCE 92 (les autres flux sont gardés).
# On peut le relancer sans risque : chaque étape déjà faite est sautée.
# Guide complet : plateforme/INSTALLATION.md
set -euo pipefail

DEPOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NR="${NODE_RED_DIR:-$HOME/.node-red}"
BASE="$NR/pce92.db"
A_IMPORTER="$NR/pce92_a_importer.json"

ok()    { echo "  OK   $*"; }
info()  { echo "  ...  $*"; }
stop()  { echo; echo "  STOP $*"; exit 1; }

echo "Dépôt     : $DEPOT"
echo "Node-RED  : $NR"
echo

echo "1. Node-RED"
command -v node-red >/dev/null 2>&1 || stop "Node-RED n'est pas installé. Installe-le avec la commande officielle :
       bash <(curl -sL https://github.com/node-red/linux-installers/releases/latest/download/update-nodejs-and-nodered-deb)
       puis lance-le une fois (node-red-start), attends « Started flows », arrête-le (node-red-stop) et relance ce script."
[ -f "$NR/settings.js" ] || stop "$NR/settings.js n'existe pas encore. Lance Node-RED une fois (node-red-start),
       attends « Started flows », arrête-le (node-red-stop) et relance ce script."
ok "Node-RED installé, réglages dans $NR/settings.js"

echo "2. Modules Node-RED (tableaux de bord, SQLite)"
if [ -d "$NR/node_modules/@flowfuse/node-red-dashboard" ] && [ -d "$NR/node_modules/node-red-node-sqlite" ]; then
    ok "déjà installés"
else
    info "installation (quelques minutes sur un Pi)"
    (cd "$NR" && npm install --no-fund --no-audit @flowfuse/node-red-dashboard node-red-node-sqlite)
    ok "installés"
fi

echo "3. Décodeur (codec S1) dans settings.js"
CODEC="$DEPOT/trame/decodeur/codec.js"
[ -f "$CODEC" ] || stop "$CODEC introuvable : le dépôt est-il complet ?"
if grep -q "trame/decodeur/codec.js" "$NR/settings.js"; then
    ok "déjà déclaré"
    grep -n "trame/decodeur/codec.js" "$NR/settings.js" | grep -q "$CODEC" \
        || info "attention : settings.js pointe vers un autre dossier que $CODEC"
else
    # La vraie ligne « functionGlobalContext: { » (pas celle du commentaire, qui commence par *).
    grep -qE '^[[:space:]]*functionGlobalContext:[[:space:]]*\{' "$NR/settings.js" \
        || stop "ligne « functionGlobalContext: { » introuvable dans settings.js : ajoute le codec à la main (plateforme/flows/README.md)."
    cp "$NR/settings.js" "$NR/settings.js.avant_pce92"
    sed -i -E "0,/^[[:space:]]*functionGlobalContext:[[:space:]]*\{/s##&\n        codec: require(\"$CODEC\"),#" "$NR/settings.js"
    node -e "require('$NR/settings.js')" >/dev/null 2>&1 \
        || { cp "$NR/settings.js.avant_pce92" "$NR/settings.js"; stop "settings.js modifié est invalide : remis comme avant."; }
    ok "ajouté (copie de l'ancien fichier : settings.js.avant_pce92)"
fi

echo "4. Fichier à importer dans Node-RED"
DEPOT="$DEPOT" BASE="$BASE" SORTIE="$A_IMPORTER" node -e '
const fs = require("fs"), p = process.env;
const fichiers = ["plateforme/flows/s2_reception.json", "plateforme/dashboards/dashboard_mvp.json",
                  "plateforme/flows/s3_stockage.json"];
const vus = new Set(), noeuds = [];
for (const f of fichiers) {
    for (const n of JSON.parse(fs.readFileSync(p.DEPOT + "/" + f, "utf8"))) {
        if (vus.has(n.id)) continue;
        vus.add(n.id);
        if (n.type === "sqlitedb") n.db = p.BASE;   // chemin de la base sur ce Pi
        noeuds.push(n);
    }
}
fs.writeFileSync(p.SORTIE, JSON.stringify(noeuds, null, 1));
'
ok "$A_IMPORTER (S2 + tableaux de bord + S3, base : $BASE)"

echo "5. Moteur d'alerte"
if python3 -c "import paho.mqtt.client" 2>/dev/null; then
    ok "module paho-mqtt présent"
else
    info "installation de paho-mqtt (mot de passe du Pi demandé)"
    sudo apt-get install -y python3-paho-mqtt
    ok "module paho-mqtt installé"
fi
# Le moteur cherche la base « pce92.db » dans le dossier d'où on le lance (la racine du dépôt) :
# on y met un lien vers la base de Node-RED. Les fichiers .db sont ignorés par git.
if [ -e "$DEPOT/pce92.db" ] || [ -L "$DEPOT/pce92.db" ]; then
    ok "lien $DEPOT/pce92.db déjà présent"
else
    ln -s "$BASE" "$DEPOT/pce92.db"
    ok "lien $DEPOT/pce92.db -> $BASE"
fi

echo "6. Capteurs connus (plateforme/config/seuils.csv)"
tail -n +2 "$DEPOT/plateforme/config/seuils.csv" | while IFS=, read -r id site seuil || [ -n "$id" ]; do
    echo "       node_id $id : $site, seuil ${seuil%$'\r'} mm"
done
echo "       Le node_id envoyé par l'émulateur doit être dans cette liste (sinon : ajouter une ligne)."

echo "7. Déploiement dans Node-RED"
manuel() {
    cat <<FIN
  ...  $1
       À faire à la main : node-red-restart, puis dans un navigateur sur le Pi :
       http://localhost:1880 -> menu ☰ -> Import -> select a file to import
       -> $A_IMPORTER -> Import -> Deploy
FIN
}
if command -v node-red-restart >/dev/null 2>&1; then
    info "redémarrage de Node-RED (pour charger le codec et les modules)"
    node-red-restart >/dev/null 2>&1 || true
fi
pret=""
for _ in $(seq 1 60); do
    curl -fs http://localhost:1880/flows -o /dev/null 2>/dev/null && { pret=1; break; }
    sleep 2
done
if [ -z "$pret" ]; then
    manuel "Node-RED ne répond pas sur http://localhost:1880 (lancé ? node-red-start)"
else
    # Garde les flux existants, remplace les nœuds PCE 92 déjà présents (mêmes identifiants).
    if curl -fs http://localhost:1880/flows -o "$NR/.flux_actuels.json" \
       && A_IMPORTER="$A_IMPORTER" ACTUELS="$NR/.flux_actuels.json" node -e '
const fs = require("fs"), p = process.env;
const nouveaux = JSON.parse(fs.readFileSync(p.A_IMPORTER, "utf8"));
const ids = new Set(nouveaux.map(n => n.id));
const actuels = JSON.parse(fs.readFileSync(p.ACTUELS, "utf8")).filter(n => !ids.has(n.id));
fs.writeFileSync(p.ACTUELS, JSON.stringify(actuels.concat(nouveaux)));
' \
       && curl -fs -X POST http://localhost:1880/flows -H "Content-Type: application/json" \
            -H "Node-RED-Deployment-Type: full" --data-binary @"$NR/.flux_actuels.json" -o /dev/null; then
        rm -f "$NR/.flux_actuels.json"
        sleep 3
        if curl -fs http://localhost:1880/dashboard -o /dev/null; then
            ok "flux S2, S3 et tableaux de bord déployés"
        else
            manuel "flux envoyés, mais le tableau de bord ne répond pas : regarde le journal (node-red-log)"
        fi
    else
        manuel "déploiement automatique impossible (Node-RED protégé par un mot de passe ?)"
    fi
fi

cat <<FIN

Suite (détails : plateforme/INSTALLATION.md) :
  - Moteur d'alerte, dans un autre terminal :
      cd "$DEPOT" && python3 plateforme/config/moteur_alerte.py
  - Tableaux de bord : http://<IP du Pi>:1880/dashboard   (IP du Pi : hostname -I)
  - Vérifier la réception : http://<IP du Pi>:1880, onglet « S2 – Réception des trames »
FIN
