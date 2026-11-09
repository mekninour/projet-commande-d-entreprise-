"""PCE 92 – S5 – Tests de l'injecteur (sans broker MQTT).

Lancer depuis ce dossier :  python test_injecteur.py
Vérifie que :
  1. les trames fabriquées sont identiques aux trames de référence partagées
     (trame/exemples/exemples_trames.csv) ;
  2. chaque trame de chaque scénario est relue correctement par le codec S1.
"""

import csv
import sys

from injecteur import RACINE_DEPOT, decoder_avec_codec, encoder_trame, volts_vers_5mv
from scenarios import SCENARIOS, generer

SEUIL = 300
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
        water = int(ligne["water_mm"])
        octets = encoder_trame(
            int(ligne["node_id"]), None if water == 65535 else water, int(ligne["batt_raw"]),
            int(ligne["seq"]), int(ligne["status"]) & 1 == 1, int(ligne["next_min"]),
        )
        attendu = bytes.fromhex(ligne["hex"])
        verifier(ligne["nom"], octets == attendu, f"obtenu {octets.hex(' ')} au lieu de {ligne['hex']}")

print("Scénarios relus par le codec S1")
for nom in sorted(SCENARIOS):
    etapes = generer(nom, SEUIL)
    alertes = [e["water_mm"] is not None and e["water_mm"] >= SEUIL for e in etapes]
    trames = [encoder_trame(3, e["water_mm"], volts_vers_5mv(e["batt_v"]), i + 1, a, 30)
              for i, (e, a) in enumerate(zip(etapes, alertes))]
    resultats = decoder_avec_codec(trames)
    ok = all(
        "data" in r
        and r["data"]["water_valid"] == (e["water_mm"] is not None)
        and (e["water_mm"] is None or r["data"]["water_mm"] == e["water_mm"])
        and (r["data"]["batt_v"] is None) == (e["batt_v"] is None)
        and (e["batt_v"] is None or abs(r["data"]["batt_v"] - e["batt_v"]) < 0.003)
        and r["data"]["seq"] == i + 1
        and r["data"]["alert"] == a
        and r["data"]["next_min"] == 30
        for i, (e, a, r) in enumerate(zip(etapes, alertes, resultats))
    )
    verifier(f"{nom} ({len(etapes)} trames)", ok)

print(f"\n{reussis} réussi(s), {echecs} échec(s)")
sys.exit(1 if echecs else 0)
