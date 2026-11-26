"""PCE 92 – S5 – Tests de l'injecteur (sans broker MQTT).

Lancer depuis ce dossier :  python test_injecteur.py
Vérifie que :
  1. les trames fabriquées sont identiques aux trames de référence partagées
     (trame/exemples/exemples_trames.csv) ;
  2. chaque trame de chaque scénario est relue correctement par le codec S1 ;
  3. les seq des pertes, des coupures et des renvois sont ceux attendus.
"""

import csv
import sys
from datetime import datetime, timezone

from injecteur import RACINE_DEPOT, decoder_avec_codec, encoder_trame, planifier, volts_vers_5mv
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

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def plan(nom, **options):
    return planifier(generer(nom, SEUIL, **options), 1, 1800, T0)


print("Scénarios relus par le codec S1")
for nom in sorted(SCENARIOS):
    envois = plan(nom)
    etapes = [env["etape"] for env in envois]
    alertes = [e["water_mm"] is not None and e["water_mm"] >= SEUIL for e in etapes]
    trames = [encoder_trame(3, e["water_mm"], volts_vers_5mv(e["batt_v"]), env["seq"], a, 30)
              for env, e, a in zip(envois, etapes, alertes)]
    resultats = decoder_avec_codec(trames)
    ok = all(
        "data" in r
        and r["data"]["water_valid"] == (e["water_mm"] is not None)
        and (e["water_mm"] is None or r["data"]["water_mm"] == e["water_mm"])
        and (r["data"]["batt_v"] is None) == (e["batt_v"] is None)
        and (e["batt_v"] is None or abs(r["data"]["batt_v"] - e["batt_v"]) < 0.003)
        and r["data"]["seq"] == env["seq"]
        and r["data"]["alert"] == a
        and r["data"]["next_min"] == 30
        for env, e, a, r in zip(envois, etapes, alertes, resultats)
    )
    verifier(f"{nom} ({len(envois)} envois)", ok)


def seqs(envois, type_):
    return [env["seq"] for env in envois if env["type"] == type_]


print("Pertes, coupures et renvois")
envois = plan("trame_perdue")
perdues = seqs(envois, "perdue")
verifier("trame_perdue : 3 pertes isolées, jamais voisines, ni la 1re ni la dernière",
         len(perdues) == 3 and all(b - a > 1 for a, b in zip(perdues, perdues[1:]))
         and 1 not in perdues and len(envois) not in perdues, f"pertes {perdues}")
verifier("trame_perdue : même graine = mêmes pertes", seqs(plan("trame_perdue"), "perdue") == perdues)
verifier("trame_perdue : autre graine = autres pertes",
         seqs(plan("trame_perdue", graine=7), "perdue") != perdues)
envois = plan("trame_perdue", coupure=5)
perdues = seqs(envois, "perdue")
suites = [p for p in perdues if p + 1 in perdues or p - 1 in perdues]
verifier("trame_perdue --coupure 5 : 5 pertes d'affilée + 3 isolées",
         len(perdues) == 8 and len(suites) == 5 and suites == list(range(suites[0], suites[0] + 5)),
         f"pertes {perdues}")

envois = plan("doublon")
verifier("doublon : la seq 4 revient après la seq 7, identique",
         [env["seq"] for env in envois] == [1, 2, 3, 4, 5, 6, 7, 4, 8, 9, 10]
         and envois[7]["type"] == "renvoi" and envois[7]["etape"] is envois[3]["etape"])
verifier("doublon : le renvoi arrive entre la seq 7 et la seq 8",
         envois[6]["recu_a"] < envois[7]["recu_a"] < envois[8]["recu_a"])

envois = plan("retransmission_differee")
verifier("retransmission_differee : seq 5 à 7 perdues, puis renvoi des seq 4 à 7 après la seq 9",
         seqs(envois, "perdue") == [5, 6, 7] and seqs(envois, "renvoi") == [4, 5, 6, 7]
         and [env["seq"] for env in envois][8:14] == [9, 4, 5, 6, 7, 10])
verifier("retransmission_differee : la seq 10 garde son créneau habituel (9 × 30 min)",
         next(env for env in envois if env["seq"] == 10)["recu_a"] == T0.replace(hour=16, minute=30))

print(f"\n{reussis} réussi(s), {echecs} échec(s)")
sys.exit(1 if echecs else 0)
