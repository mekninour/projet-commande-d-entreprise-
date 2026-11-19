// =============================================================================
// PCE 92 – S1 – Décodeur de la trame capteur (12 octets) – contrat v1.2 (V1)
// Binôme B1 – Nour Mekni
//
// Utilisable dans Node-RED (nœud function) ou dans ChirpStack v4 (codec JavaScript) :
// la fonction decodeUplink({ bytes: [...] }) est la même dans les deux cas.
//
// Format V1 (docs/contrat_interface.md, big-endian) :
//   octets 0-1  node_id   uint16  1 à 65535 ; 0 interdit -> trame rejetée
//   octets 2-3  water_mm  uint16  niveau d'eau au-dessus du sol ; 0xFFFF = mesure invalide
//   octet  4    batt_5mv  uint8   V = 2,50 + n × 0,005 ; 0xFF = tension inconnue
//   octets 5-6  seq       uint16  compteur de trames, repasse à 0 après 65535
//   octet  7    status    uint8   bit 0 = alerte seuil (niveau >= 300 mm) ; bits 1-7 à 0
//   octet  8    next_min  uint8   minutes avant la prochaine trame (1 à 254) ; 0xFF = inconnue
//   octets 9-11 réservés          émis à 0x00, ignorés en réception
// L'horodatage n'est pas dans la trame : il est ajouté à la réception (règle 4 du contrat).
// =============================================================================

var CONFIG = {
  BATT_OFFSET_V: 2.5,  // tension pour n = 0
  BATT_STEP_V: 0.005,  // 5 mV par unité
  ALERT_MASK: 1        // bit 0 du status
};

var FRAME_SIZE = 12;
var WATER_INVALID = 65535; // 0xFFFF
var UNKNOWN_BYTE = 255;    // 0xFF

// 1er octet × 256 + 2e octet
function readUint16(b, i) {
  return b[i] * 256 + b[i + 1];
}

// Point d'entrée. input = { bytes: [12 nombres de 0 à 255], ... }
function decodeUplink(input) {
  var b = input.bytes;
  var warnings = [];

  // Règle : trame de longueur fixe.
  if (!b || b.length !== FRAME_SIZE) {
    return {
      errors: ["taille de trame invalide : " + (b ? b.length : 0) + " octets au lieu de " + FRAME_SIZE]
    };
  }

  var nodeId = readUint16(b, 0);
  var waterMm = readUint16(b, 2);
  var batt5mv = b[4];
  var seq = readUint16(b, 5);
  var status = b[7];
  var nextMin = b[8];

  // Règle 1 du contrat : node_id = 0 -> trame rejetée.
  if (nodeId === 0) {
    return { errors: ["node_id = 0 : trame rejetée (règle 1 du contrat)"] };
  }

  // Règle 2 : valeurs spéciales.
  var waterValid = waterMm !== WATER_INVALID;
  var battV = null;
  if (batt5mv !== UNKNOWN_BYTE) {
    battV = Math.round((CONFIG.BATT_OFFSET_V + batt5mv * CONFIG.BATT_STEP_V) * 1000) / 1000;
  }

  // Règle 3 : seul le bit 0 compte ; les autres doivent être à 0 (ignorés, mais signalés).
  var alert = (status & CONFIG.ALERT_MASK) !== 0;
  if ((status & (255 - CONFIG.ALERT_MASK)) !== 0) {
    warnings.push("status : bits 1 à 7 non nuls (0x" + status.toString(16) + "), ignorés en V1");
  }

  // next_min : 1 à 254, 0xFF = inconnue.
  if (nextMin === 0) {
    warnings.push("next_min = 0 (le contrat impose 1 à 254)");
  }

  return {
    data: {
      node_id: nodeId,
      water_mm: waterMm,
      water_valid: waterValid,
      batt_5mv: batt5mv,
      batt_v: battV,
      seq: seq,
      status: status,
      alert: alert,
      next_min: nextMin === UNKNOWN_BYTE ? null : nextMin
    },
    warnings: warnings
  };
}

// Export pour les tests et pour Node.js (ignoré par ChirpStack).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { decodeUplink: decodeUplink, CONFIG: CONFIG };
}
