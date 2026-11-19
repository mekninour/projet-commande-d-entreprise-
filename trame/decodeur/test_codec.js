// PCE 92 – S1 – Tests du décodeur (contrat v1.2). Lancer depuis la racine du dépôt :
//   node trame/decodeur/test_codec.js
// Aucun paquet à installer. Code de sortie 0 = tout est bon.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { decodeUplink } = require("./codec.js");

const CSV = path.join(__dirname, "..", "exemples", "exemples_trames.csv");
const toBytes = (hex) => hex.replace(/\s+/g, "").match(/../g).map((h) => parseInt(h, 16));
const decode = (hex) => decodeUplink({ bytes: toBytes(hex) });

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
    const d = res.data;
    assert.strictEqual(d.node_id, Number(row.node_id), "node_id");
    assert.strictEqual(d.water_mm, Number(row.water_mm), "water_mm");
    assert.strictEqual(d.batt_5mv, Number(row.batt_raw), "batt_5mv");
    assert.strictEqual(d.seq, Number(row.seq), "seq");
    assert.strictEqual(d.status, Number(row.status), "status");
    assert.strictEqual(d.next_min, row.next_min === "255" ? null : Number(row.next_min), "next_min");
  });
}

// --- 2. Interprétation des champs (contrat v1.2) ------------------------------
console.log("Interprétation des champs");
test("exemple officiel : 310 mm, 3,15 V, alerte, prochain envoi 5 min", () => {
  const d = decode("000301368200 9D 01 05 000000").data;
  assert.deepStrictEqual([d.water_mm, d.water_valid, d.batt_v, d.alert, d.next_min], [310, true, 3.15, true, 5]);
});
test("batterie : 0x00 -> 2,50 V et 0xFE -> 3,77 V", () => {
  assert.strictEqual(decode("0003002D00009E001E000000").data.batt_v, 2.5);
  assert.strictEqual(decode("0003002DFE009E001E000000").data.batt_v, 3.77);
});
test("valeurs spéciales : water 0xFFFF invalide, batterie 0xFF et next_min 0xFF inconnus", () => {
  const d = decode("000CFFFFFFFFFF00FF000000").data;
  assert.deepStrictEqual([d.water_valid, d.batt_v, d.next_min], [false, null, null]);
});
test("status 0x00 -> pas d'alerte", () => {
  assert.strictEqual(decode("0003002DA0009E001E000000").data.alert, false);
});
test("status 0x80 (ancienne convention MSB) -> pas d'alerte + avertissement", () => {
  const res = decode("0003002DA0009E801E000000");
  assert.strictEqual(res.data.alert, false);
  assert.ok(res.warnings.some((w) => w.includes("bits 1 à 7")));
});
test("octets réservés 9-11 non nuls -> ignorés", () => {
  const res = decode("0003002DA0009E001EABCDEF");
  assert.deepStrictEqual(res.warnings, []);
  assert.strictEqual(res.data.water_mm, 45);
});

// --- 3. Trames rejetées ou suspectes -------------------------------------------
console.log("Trames rejetées ou suspectes");
test("trame de 4 octets -> erreur", () => {
  assert.ok(decode("00030136").errors[0].includes("taille de trame invalide"));
});
test("node_id = 0 -> trame rejetée (règle 1)", () => {
  assert.ok(decode("0000013682009D0105000000").errors[0].includes("node_id = 0"));
});
test("next_min = 0 -> avertissement", () => {
  assert.ok(decode("0003002DA0009E0000000000").warnings.some((w) => w.includes("next_min = 0")));
});

console.log(`\n${passed} réussi(s), ${failed} échec(s)`);
process.exit(failed ? 1 : 0);
