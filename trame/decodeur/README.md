# Décodeur ChirpStack (S1)

**Binôme :** B1 – Nour Mekni

Codec JavaScript qui transforme les 12 octets de la trame en champs lisibles, conformément au [contrat d'interface](../../docs/contrat_interface.md).

| Fichier | Rôle |
|---|---|
| `codec.js` | Le décodeur, à coller tel quel dans ChirpStack |
| `test_codec.js` | Tests : relit `../exemples/exemples_trames.csv`, puis teste l'interprétation et l'extension S4 |

## Tester

Depuis la racine du dépôt (Node.js requis, aucun paquet à installer) :

```
node trame/decodeur/test_codec.js
```

## Installer dans ChirpStack v4

*Device profiles* > le profil EU868 classe A OTAA > onglet *Codec* > **JavaScript functions** > coller tout `codec.js` > *Submit*. Le résultat apparaît dans le champ `object` des événements `up` (interface web et MQTT).

## Sortie

```json
{ "node_id": 3, "water_mm": 1240, "batt_cv": 158, "batt_v": 3.16, "seq": 157, "status": 0,
  "alert": false, "sensor_fault": false, "eco_mode": false,
  "format_version": 0, "step_min": 0,
  "measurements": [ { "index": 0, "offset_min": 0, "water_mm": 1240, "time": "2026-11-02T10:00:00.000Z" } ] }
```

- `measurements` contient toujours la mesure actuelle. Avec l'extension S4, il contient aussi les 3 mesures précédentes, datées à rebours depuis l'heure de réception. **C'est cette liste que la plateforme stocke.**
- Une trame qui n'a pas 12 octets renvoie une erreur. Les incohérences (node_id nul, batterie hors 2,0–4,2 V, bit de status inconnu, version inconnue) renvoient un avertissement, et la trame reste décodée.

## Hypothèses (paramètres en tête de `codec.js`)

| Point ouvert du contrat | Hypothèse retenue | Paramètre |
|---|---|---|
| n°1 – unité de `batt_cv` | 20 mV par unité | `BATT_MV_PER_UNIT` |
| n°2 – bits de `status` | MSB : alerte 0x80 (réunion du 16/10). Défaut capteur 0x40 et mode éco 0x20 : **hypothèse B1, à confirmer** | `STATUS_FROM_MSB` |
| n°3 – datation | heure de réception par la passerelle | — |

## Extension S4 des octets 8–11 (proposition, à valider avec B2 puis Brest)

| Octet | Contenu |
|---|---|
| 8 | 4 bits hauts = version du format (0 = aucune extension, 1 = S4) ; 4 bits bas = pas de mesure en minutes (5 ou 15) |
| 9, 10, 11 | écart en cm, entier signé : mesure actuelle − mesure précédente 1, 2, 3 |

Ces trames ne sont pas dans `exemples_trames.csv` tant que la convention n'est pas validée, parce que l'encodeur ne sait pas encore les produire.
