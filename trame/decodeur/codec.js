// =============================================================================
// PCE 92 – S1 – Décodeur ChirpStack v4 de la trame capteur (12 octets)
// Binôme B1 – Nour Mekni
// ChirpStack appelle decodeUplink() à chaque trame reçue et place le résultat
// dans le champ "object" de l'événement "up" publié sur MQTT.
//
// Format (docs/contrat_interface.md, big-endian) :
//   octets 0-1  node_id   uint16
//   octets 2-3  water_mm  uint16
//   octet  4    batt_cv   uint8   (voir BATT_MV_PER_UNIT, point ouvert n°1)
//   octets 5-6  seq       uint16
//   octet  7    status    uint8   champ de bits (voir STATUS_FROM_MSB, point ouvert n°2)
//   octets 8-11 réservés  PROPOSITION S4 (annexe B du L1), non validée par Brest :
//                 octet 8     = version (4 bits hauts) | pas de mesure en min (4 bits bas)
//                 octets 9-11 = écart en cm (int8 signé) = mesure actuelle - mesure précédente k
// =============================================================================

// ---- Hypothèses de travail (à changer ici si Brest décide autrement) --------
var CONFIG = {
  // Point ouvert n°1 : 158 -> 3,16 V, donc 20 mV par unité.
  BATT_MV_PER_UNIT: 20,
  // Point ouvert n°2 : bit d'alerte = MSB (0x80), réunion du 16/10.
  // Les bits suivants (défaut capteur 0x40, mode éco 0x20) sont une hypothèse B1.
  STATUS_FROM_MSB: true,
  // Plage utile de la batterie (contrat) : hors plage -> avertissement.
  BATT_MIN_V: 2.0,
  BATT_MAX_V: 4.2
};

var FRAME_SIZE = 12;

// Drapeaux de status, dans l'ordre du contrat (1er, 2e, 3e bit).
var STATUS_FLAGS = ["alert", "sensor_fault", "eco_mode"];

// 1er octet × 256 + 2e octet
function readUint16(b, i) {
  return b[i] * 256 + b[i + 1];
}

function toInt8(byte) {
  return byte > 127 ? byte - 256 : byte;
}

function bitPosition(rank) {
  return CONFIG.STATUS_FROM_MSB ? 7 - rank : rank;
}

function decodeStatus(byte, warnings) {
  var flags = {};
  var knownMask = 0;
  for (var r = 0; r < STATUS_FLAGS.length; r++) {
    var mask = Math.pow(2, bitPosition(r)); // ex. position 7 -> 128 (0x80)
    flags[STATUS_FLAGS[r]] = (byte & mask) !== 0;
    knownMask = knownMask + mask;
  }
  // Un bit inattendu signale souvent une convention différente côté encodeur.
  if ((byte & (255 - knownMask)) !== 0) {
    warnings.push("status : bits inconnus levés (0x" + byte.toString(16) + ")");
  }
  return flags;
}

function decodeReserved(b, waterMm, recvTime, warnings) {
  var version = Math.floor(b[8] / 16); // 4 bits hauts
  var stepMin = b[8] % 16;             // 4 bits bas
  var measurements = [{ index: 0, offset_min: 0, water_mm: waterMm }];

  if (version === 0) {
    if (b[8] !== 0 || b[9] !== 0 || b[10] !== 0 || b[11] !== 0) {
      warnings.push("octets réservés non nuls alors que la version vaut 0");
    }
  } else if (version === 1) {
    if (stepMin === 0) {
      warnings.push("version 1 mais pas de mesure nul");
    }
    for (var k = 1; k <= 3; k++) {
      var deltaCm = toInt8(b[8 + k]);
      var previous = waterMm - deltaCm * 10;
      if (previous < 0) {
        warnings.push("mesure précédente n°" + k + " négative (" + previous + " mm)");
      }
      measurements.push({ index: k, offset_min: -k * stepMin, water_mm: previous });
    }
  } else {
    warnings.push("version de format inconnue : " + version + " (octets 8-11 ignorés)");
  }

  // Datation par l'heure de réception (la trame ne porte pas d'heure, point ouvert n°3).
  if (recvTime) {
    var t0 = new Date(recvTime).getTime();
    if (!isNaN(t0)) {
      for (var m = 0; m < measurements.length; m++) {
        measurements[m].time = new Date(t0 + measurements[m].offset_min * 60000).toISOString();
      }
    }
  }

  return { version: version, stepMin: stepMin, measurements: measurements };
}

// Point d'entrée appelé par ChirpStack v4.
// input = { bytes: [..], fPort: n, recvTime: Date, variables: {..} }
function decodeUplink(input) {
  var b = input.bytes;
  var warnings = [];

  if (!b || b.length !== FRAME_SIZE) {
    return {
      errors: ["taille de trame invalide : " + (b ? b.length : 0) + " octets au lieu de " + FRAME_SIZE]
    };
  }

  var nodeId = readUint16(b, 0);
  var waterMm = readUint16(b, 2);
  var battCv = b[4];
  var battV = Math.round(battCv * CONFIG.BATT_MV_PER_UNIT) / 1000;
  var seq = readUint16(b, 5);

  if (nodeId === 0) {
    warnings.push("node_id = 0 (le contrat impose 1 à 65535)");
  }
  if (battV < CONFIG.BATT_MIN_V || battV > CONFIG.BATT_MAX_V) {
    warnings.push("batterie hors plage utile : " + battV + " V");
  }

  var reserved = decodeReserved(b, waterMm, input.recvTime, warnings);
  var flags = decodeStatus(b[7], warnings);

  return {
    data: {
      node_id: nodeId,
      water_mm: waterMm,
      batt_cv: battCv,
      batt_v: battV,
      seq: seq,
      status: b[7],
      alert: flags.alert,
      sensor_fault: flags.sensor_fault,
      eco_mode: flags.eco_mode,
      format_version: reserved.version,
      step_min: reserved.stepMin,
      measurements: reserved.measurements
    },
    warnings: warnings
  };
}

// Export pour les tests sous Node.js (ignoré par ChirpStack).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { decodeUplink: decodeUplink, CONFIG: CONFIG };
}