// PCE 92 – S2 – Tests du flux de réception (sans Node-RED ni broker MQTT).
//
// Lancer depuis ce dossier :  node test_s2.js
// Le test lit les deux fonctions du flux s2_reception.json (« 1. Décoder » et
// « 2. Contrôler seq ») et les exécute comme Node-RED, sur des suites de trames :
// pertes, doublon immédiat, doublon en retard, trames en retard, redémarrage du nœud.
// Il lit aussi « 0. Lire ChirpStack » et vérifie qu'un uplink LoRaWAN donne la même mesure.

const fs = require("fs");
const path = require("path");
const codec = require(path.join(__dirname, "..", "..", "trame", "decodeur", "codec.js"));

const flux = JSON.parse(fs.readFileSync(path.join(__dirname, "s2_reception.json"), "utf8"));
const code = nom => flux.find(n => n.type === "function" && n.name.startsWith(nom)).func;
const decoder = new Function("msg", "node", "flow", "global", code("1."));
const controler = new Function("msg", "node", "flow", "global", code("2."));
const lireChirpstack = new Function("msg", "node", "flow", "global", "Buffer", code("0."));

let reussis = 0, echecs = 0;
function verifier(nom, condition, detail) {
    if (condition) { reussis++; console.log("  OK     " + nom); }
    else { echecs++; console.log("  ÉCHEC  " + nom + (detail ? "  " + detail : "")); }
}

// Contexte Node-RED minimal : mémoire « flow » partagée entre les trames d'une même suite.
function nouveauFlux() {
    const memoire = {};
    const flow = { get: k => memoire[k], set: (k, v) => { memoire[k] = v; } };
    const global = { get: k => (k === "codec" ? codec : undefined) };
    const node = { status() {}, warn() {}, error() {} };
    return function recevoir(seq, water_mm, minute) {
        const octets = [0, 3, water_mm >> 8, water_mm & 255, 0xA0, seq >> 8, seq & 255, 0, 30, 0, 0, 0];
        const hex = octets.map(o => o.toString(16).padStart(2, "0")).join("").toUpperCase();
        const recu = new Date(Date.UTC(2026, 10, 19, 0, 0) + minute * 60000).toISOString();
        const [mesure] = decoder({ payload: { received_at: recu, payload_hex: hex, source: "test" } }, node, flow, global);
        const [acceptee, evenement] = controler(mesure, node, flow, global);
        return { mesure: acceptee ? acceptee.payload : null, evt: evenement ? evenement.payload : null };
    };
}

// Envoie une suite [seq, water_mm] (une trame toutes les 30 min) et renvoie les sorties.
function suite(trames) {
    const recevoir = nouveauFlux();
    return trames.map(([seq, water], i) => recevoir(seq, water, i * 30));
}

console.log("Cas déjà gérés");
let r = suite([[1, 30], [2, 31], [3, 32]]);
verifier("trames normales : 3 mesures, aucun événement", r.every(x => x.mesure && !x.evt));
r = suite([[1, 30], [2, 31], [5, 32]]);
verifier("seq 2 puis 5 : mesure gardée, 2 trames perdues",
         r[2].mesure && r[2].mesure.lost_before === 2 && r[2].evt.type === "trames_perdues" && r[2].evt.nombre === 2);
r = suite([[1, 30], [2, 31], [2, 31]]);
verifier("doublon immédiat : écarté, événement doublon (pas en retard)",
         !r[2].mesure && r[2].evt.type === "doublon" && r[2].evt.en_retard === false);

console.log("Doublon en retard (scénario doublon)");
r = suite([[1, 30], [2, 31], [3, 32], [4, 33], [5, 34], [6, 35], [7, 36], [4, 33], [8, 37]]);
verifier("seq 4 revient après la 7, identique : écartée, événement doublon en retard",
         !r[7].mesure && r[7].evt.type === "doublon" && r[7].evt.en_retard === true && r[7].evt.retard_trames === 3);
verifier("la seq 8 suivante est normale (pas de fausses pertes)", r[8].mesure && !r[8].evt && r[8].mesure.lost_before === 0);

console.log("Trames en retard (scénario retransmission_differee)");
r = suite([[1, 30], [2, 31], [3, 32], [4, 33], [8, 37], [9, 38], [4, 33], [5, 34], [6, 35], [7, 36], [10, 39]]);
verifier("seq 4 puis 8 : 3 trames perdues (5, 6, 7)", r[4].evt.type === "trames_perdues" && r[4].evt.nombre === 3);
verifier("renvoi de la seq 4, déjà reçue : doublon en retard", !r[6].mesure && r[6].evt.type === "doublon" && r[6].evt.en_retard);
const retards = r.slice(7, 10);
verifier("seq 5, 6, 7 renvoyées : pas publiées comme mesures actuelles", retards.every(x => !x.mesure));
verifier("seq 5, 6, 7 renvoyées : événement trame_en_retard avec la mesure",
         retards.every((x, i) => x.evt.type === "trame_en_retard" && x.evt.seq === 5 + i && x.evt.water_mm === 34 + i));
verifier("heure de mesure estimée de la seq 5 = seq 9 − 4 × 30 min",
         retards[0].evt.mesure_estimee_a === new Date(Date.UTC(2026, 10, 19, 2, 30) - 4 * 30 * 60000).toISOString(),
         retards[0].evt.mesure_estimee_a);
verifier("la seq 10 suivante est normale", r[10].mesure && !r[10].evt);

console.log("Même trame en retard reçue deux fois");
r = suite([[1, 30], [3, 32], [2, 31], [2, 31]]);
verifier("1re fois : trame en retard ; 2e fois : doublon en retard",
         r[2].evt.type === "trame_en_retard" && r[3].evt.type === "doublon" && r[3].evt.en_retard);

console.log("Redémarrage du nœud");
r = suite([[1, 30], [2, 31], [3, 32], [4, 33], [1, 50], [2, 51]]);
verifier("seq 4 puis 1 avec une autre mesure : retour de seq, mesure gardée",
         r[4].mesure && r[4].evt.type === "retour_seq" && r[4].evt.seq_precedent === 4);
verifier("après le redémarrage, la seq 2 est normale (mémoire repartie de zéro)", r[5].mesure && !r[5].evt);
r = suite([[1, 30], [2, 31], [3, 32], [1, 30]]);
verifier("seq 1 identique qui revient : doublon en retard (pas un redémarrage)",
         !r[3].mesure && r[3].evt.type === "doublon" && r[3].evt.en_retard);

console.log("Mémoire limitée aux 64 dernières trames");
const longue = [];
for (let s = 1; s <= 80; s++) longue.push([s, 30]);
longue.push([5, 30]);
r = suite(longue);
verifier("seq 5 qui revient 75 trames plus tard : trop ancienne, traitée comme un redémarrage",
         r[80].mesure && r[80].evt.type === "retour_seq");

console.log("Uplinks ChirpStack (LoRaWAN privé)");
{
    const memoire = {};
    const flow = { get: k => memoire[k], set: (k, v) => { memoire[k] = v; } };
    const global = { get: k => (k === "codec" ? codec : undefined) };
    const node = { status() {}, warn() {}, error() {} };
    // Trame officielle du contrat v1.2 : nœud 3, 268 mm, 3,30 V, seq 4660, alerte levée, 30 min.
    const octets = Buffer.from("0003010CA0123401001E0000", "hex");
    const up = {
        deduplicationId: "x", time: "2026-11-20T10:00:00.000Z",
        deviceInfo: { devEui: "0000000000000001", deviceName: "noeud-3" },
        fPort: 1, fCnt: 17, data: octets.toString("base64"),
        object: { water_mm: 9999 },
        rxInfo: [{ rssi: -110, snr: 2.5 }, { rssi: -95, snr: 6.0 }]
    };
    const entree = lireChirpstack({ payload: up }, node, flow, global, Buffer).payload;
    verifier("data (base64) -> payload_hex", entree.payload_hex === "0003010CA0123401001E0000", entree.payload_hex);
    verifier("meilleure réception gardée (RSSI −95, SNR 6)", entree.rssi === -95 && entree.snr === 6);
    verifier("heure de réception = time de ChirpStack", entree.received_at === "2026-11-20T10:00:00.000Z");
    verifier("source chirpstack, devEui et fCnt gardés",
             entree.source === "chirpstack" && entree.dev_eui === "0000000000000001" && entree.fcnt === 17);
    const [mesure] = decoder({ payload: entree }, node, flow, global);
    verifier("décodée par le codec S1, pas par « object » : 268 mm, nœud 3, seq 4660",
             mesure && mesure.payload.water_mm === 268 && mesure.payload.node_id === 3 && mesure.payload.seq === 4660
             && mesure.topic === "pce92/mesures/3");
    const [acceptee] = controler(mesure, node, flow, global);
    verifier("puis contrôlée comme une trame point à point", acceptee && acceptee.payload.seq === 4660);

    const sansHeure = lireChirpstack({ payload: Object.assign({}, up, { time: undefined,
        rxInfo: [{ rssi: -100, snr: 1, nsTime: "2026-11-20T10:00:01.000Z" }] }) }, node, flow, global, Buffer).payload;
    verifier("sans time : heure du serveur ChirpStack (nsTime)", sansHeure.received_at === "2026-11-20T10:00:01.000Z");
    const vide = lireChirpstack({ payload: Object.assign({}, up, { data: undefined }) }, node, flow, global, Buffer).payload;
    const [m2, rejet] = decoder({ payload: vide }, node, flow, global);
    verifier("uplink sans données : rejeté (événement rejet)", !m2 && rejet.payload.type === "rejet"
             && rejet.payload.source === "chirpstack");
}

console.log("\n" + reussis + " réussi(s), " + echecs + " échec(s)");
process.exit(echecs ? 1 : 0);
