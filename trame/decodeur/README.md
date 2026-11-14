# Décodeur de la trame (S1)

**Binôme :** B1 – Nour Mekni

Code JavaScript qui transforme les 12 octets de la trame en valeurs lisibles, conformément au **contrat d'interface v1.2 (V1)**. La même fonction `decodeUplink({ bytes })` sert dans Node-RED (nœud *function*) et, si la chaîne utilise un jour LoRaWAN, dans ChirpStack.

| Fichier | Rôle |
|---|---|
| `codec.js` | Le décodeur |
| `test_codec.js` | Tests : relit `../exemples/exemples_trames.csv`, puis teste l'interprétation et les trames rejetées |

## Tester

Depuis la racine du dépôt (Node.js requis, aucun paquet à installer) :

```
node trame/decodeur/test_codec.js
```

## Sortie

Avec la trame d'exemple du contrat, `00 03 01 36 82 00 9D 01 05 00 00 00` :

```json
{ "node_id": 3, "water_mm": 310, "water_valid": true, "batt_5mv": 130, "batt_v": 3.15,
  "seq": 157, "status": 1, "alert": true, "next_min": 5 }
```

## Règles appliquées (contrat v1.2)

| Champ | Lecture | Cas particulier |
|---|---|---|
| `node_id` | octets 0-1 | 0 → **trame rejetée** (erreur) |
| `water_mm` | octets 2-3, niveau au-dessus du sol | 0xFFFF → `water_valid: false` |
| `batt_v` | 2,50 + octet 4 × 0,005 V | 0xFF → `null` (inconnue) |
| `seq` | octets 5-6 | — |
| `alert` | bit 0 de l'octet 7 | bits 1 à 7 non nuls → ignorés, avec un avertissement |
| `next_min` | octet 8, minutes avant la prochaine trame | 0xFF → `null` ; 0 → avertissement |
| octets 9-11 | réservés | ignorés |

Une trame qui n'a pas 12 octets ou dont le `node_id` vaut 0 renvoie une erreur (`errors`). Les incohérences renvoient un avertissement (`warnings`), et la trame reste décodée.

Ce qui n'est **pas** fait ici, mais à la réception (S2) : l'horodatage (règle 4), et la détection des doublons et des pertes à partir de `seq` (règle 5).
