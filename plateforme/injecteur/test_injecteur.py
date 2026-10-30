"""PCE 92 – S5 – Tests de l'injecteur (sans broker MQTT).

Lancer depuis ce dossier :  python test_injecteur.py
Vérifie que :
  1. les trames fabriquées sont identiques aux trames de référence partagées
     (trame/exemples/exemples_trames.csv) ;
  2. chaque trame de chaque scénario est relue correctement par le codec S1.
"""

import csv
import sys

from injecteur import RACINE_DEPOT, decoder_avec_codec, encoder_trame
from scenarios import SCENARIOS, generer

reussis = echecs = 0


def verifier(nom, condition, detail=""):
    global reussis, echecs
    if condition:
        reussis += 1
        print(f"  OK     {nom}")
    else:
        echecs += 1
        print(f"  ÉCHEC  {nom}  {detail}")


print("Trames partagées (exemples_trames.csv)")
with open(RACINE_DEPOT / "trame" / "exemples" / "exemples_trames.csv", encoding="utf-8") as f:
    for ligne in csv.DictReader(f):
        status = int(ligne["status"])
        octets = encoder_trame(
            int(ligne["node_id"]), int(ligne["water_mm"]), int(ligne["batt_raw"]) * 20 / 1000,
            int(ligne["seq"]), bool(status & 0x80), bool(status & 0x40), bool(status & 0x20),
        )
        attendu = bytes.fromhex(ligne["hex"])
        verifier(ligne["nom"], octets == attendu, f"obtenu {octets.hex(' ')} au lieu de {ligne['hex']}")

print("Scénarios relus par le codec S1")
for nom in sorted(SCENARIOS):
    etapes = generer(nom, seuil=2000)
    trames = [
        (encoder_trame(3, e["water_mm"], e["batt_v"], i + 1, e["alert"], e["sensor_fault"], e["eco_mode"]),
         "2026-11-02T10:00:00.000Z")
        for i, e in enumerate(etapes)
    ]
    resultats = decoder_avec_codec(trames)
    ok = all(
        "data" in r
        and r["data"]["water_mm"] == e["water_mm"]
        and r["data"]["seq"] == i + 1
        and r["data"]["alert"] == e["alert"]
        and r["data"]["sensor_fault"] == e["sensor_fault"]
        and r["data"]["eco_mode"] == e["eco_mode"]
        for i, (e, r) in enumerate(zip(etapes, resultats))
    )
    verifier(f"{nom} ({len(etapes)} trames)", ok)

print(f"\n{reussis} réussi(s), {echecs} échec(s)")
sys.exit(1 if echecs else 0)
