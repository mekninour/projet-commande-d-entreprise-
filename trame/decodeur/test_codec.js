// PCE 92 – S1 – Tests du décodeur. Lancer depuis la racine du dépôt :
//   node trame/decodeur/test_codec.js
// Aucun paquet à installer. Code de sortie 0 = tout est bon.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { decodeUplink } = require("./codec.js");

const CSV = path.join(__dirname, "..", "exemples", "exemples_trames.csv");
const toBytes = (hex) => hex.replace(/\s+/g, "").match(/../g).map((h) => parseInt(h, 16));
const decode = (hex, extra = {}) => decodeUplink({ bytes: toBytes(hex), fPort: 1, ...extra });

let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); console.log("  OK     " + name); passed++; }
  catch (e) { console.log("  ÉCHEC  " + name + "\n         " + e.message); failed++; }
}

// --- 1. Trames partagées (trame/exemples/exemples_trames.csv) ----------------
// Les mêmes lignes servent aux tests de l'encodeur : les deux ne peuvent pas diverger.
console.log("Trames partagées (exemples_trames.csv)");
const [header, ...rows] = fs.readFileSync(CSV, "utf8").trim().split(/\r?\n/);
const cols = header.split(",");
for (const line of rows) {
  const row = Object.fromEntries(line.split(",").map((v, i) => [cols[i], v]));
  test(row.nom, () => {
    const res = decode(row.hex);
    assert.ok(!res.errors, "erreurs : " + res.errors);
    assert.deepStrictEqual(res.warnings, [], "avertissements inattendus");
    assert.strictEqual(res.data.node_id, Number(row.node_id), "node_id");
    assert.strictEqual(res.data.water_mm, Number(row.water_mm), "water_mm");
    assert.strictEqual(res.data.batt_cv, Number(row.batt_raw), "batt_cv");
    assert.strictEqual(res.data.seq, Number(row.seq), "seq");
    assert.strictEqual(res.data.status, Number(row.status), "status");
  });
}

// --- 2. Interprétation (hypothèses de travail du contrat) --------------------
console.log("Interprétation des champs");
test("batterie : 158 -> 3,16 V (20 mV par unité)", () => {
  assert.strictEqual(decode("000304D89E009D0000000000").data.batt_v, 3.16);
});
test("status 0x80 -> alerte seule (MSB)", () => {
  const d = decode("0003092EBE009E8000000000").data;
  assert.deepStrictEqual([d.alert, d.sensor_fault, d.eco_mode], [true, false, false]);
});
test("status 0x60 -> défaut capteur + mode éco", () => {
  const d = decode("000C000069FFFF6000000000").data;
  assert.deepStrictEqual([d.alert, d.sensor_fault, d.eco_mode], [false, true, true]);
});
test("status 0x01 (convention LSB) -> avertissement", () => {
  assert.ok(decode("000304D89E009D0100000000").warnings.some((w) => w.includes("bits inconnus")));
});

// --- 3. Extension S4, octets 8-11 (proposition, non validée par Brest) --------
console.log("Extension S4 (proposition)");
test("vigilance, pas 5 min, montée", () => {
  const d = decode("000305DC9E00C8001503070C").data;
  assert.strictEqual(d.format_version, 1);
  assert.strictEqual(d.step_min, 5);
  assert.deepStrictEqual(d.measurements.map((m) => [m.offset_min, m.water_mm]),
    [[0, 1500], [-5, 1470], [-10, 1430], [-15, 1380]]);
});
test("veille, pas 15 min, décrue (écarts négatifs)", () => {
  const d = decode("000303849E00C9001FFEFBF7").data;
  assert.deepStrictEqual(d.measurements.map((m) => [m.offset_min, m.water_mm]),
    [[0, 900], [-15, 920], [-30, 950], [-45, 990]]);
});
test("mesures datées à rebours de l'heure de réception", () => {
  const d = decode("000305DC9E00C8001503070C", { recvTime: new Date("2026-11-02T10:00:00Z") }).data;
  assert.deepStrictEqual(d.measurements.map((m) => m.time), [
    "2026-11-02T10:00:00.000Z", "2026-11-02T09:55:00.000Z",
    "2026-11-02T09:50:00.000Z", "2026-11-02T09:45:00.000Z",
  ]);
});

// --- 4. Trames invalides ------------------------------------------------------
console.log("Trames invalides");
test("trame de 4 octets -> erreur", () => {
  assert.ok(decode("000304D8").errors[0].includes("taille de trame invalide"));
});
test("node_id = 0 -> avertissement", () => {
  assert.ok(decode("000004D89E009D0000000000").warnings.some((w) => w.includes("node_id = 0")));
});

console.log(`\n${passed} réussi(s), ${failed} échec(s)`);
process.exit(failed ? 1 : 0);
