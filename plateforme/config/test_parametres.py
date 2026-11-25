"""Tests des réglages du moteur d'alerte (AL4), sans broker MQTT.

Lancer depuis la racine du dépôt : python3 plateforme/config/test_parametres.py
"""
import json
import os
import sys
import tempfile
import types

# Le moteur importe paho-mqtt ; ces tests n'en ont pas besoin.
if "paho" not in sys.modules:
    paho = types.ModuleType("paho"); paho.mqtt = types.ModuleType("paho.mqtt")
    paho.mqtt.client = types.ModuleType("paho.mqtt.client")
    sys.modules.update({"paho": paho, "paho.mqtt": paho.mqtt, "paho.mqtt.client": paho.mqtt.client})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moteur_alerte as m  # noqa: E402

echecs = 0


def verifie(nom, condition):
    global echecs
    print(("OK    " if condition else "ECHEC ") + nom)
    if not condition:
        echecs += 1


def trame(h, minute):
    return {"water_mm": h, "received_at": f"2026-11-26T10:{minute:02d}:00Z"}


tmp = tempfile.mkdtemp()
json_path = os.path.join(tmp, "parametres_alerte.json")
csv_path = os.path.join(tmp, "seuils.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("node_id,site,seuil_alerte,montee_rapide_mm_h\n1,SITE-1,1000,\n2,SITE-2,1000,50\n")

# 1. Défauts, fichier JSON, colonne de seuils.csv
p = m.charger_parametres(None, json_path)
verifie("sans fichier : valeurs par défaut", p == m.PARAMETRES_DEFAUT)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"_aide": "x", "persistance_mesures": 3, "hysteresis_pct": "abc"}, f)
p = m.charger_parametres(None, json_path)
verifie("JSON : persistance 3 prise en compte", p["persistance_mesures"] == 3)
verifie("JSON : valeur invalide ignorée", p["hysteresis_pct"] == m.PARAMETRES_DEFAUT["hysteresis_pct"])
_, _, propres1 = m.requete_capteur(1, csv_path)
_, _, propres2 = m.requete_capteur(2, csv_path)
verifie("CSV : colonne vide = réglage commun", m.charger_parametres(propres1, json_path)["montee_rapide_mm_h"] == 200)
verifie("CSV : colonne remplie = réglage du capteur", m.charger_parametres(propres2, json_path)["montee_rapide_mm_h"] == 50)
verifie("compatibilité : requete_site_et_seuil", m.requete_site_et_seuil(2, csv_path) == ("SITE-2", 1000))

# 2. Persistance
p = dict(m.PARAMETRES_DEFAUT, persistance_mesures=3, montee_rapide_mm_h=0)
etat = {"alert": False, "nb_consecutifs_seuil": 0}
resultats = []
for h in (1100, 1100, 1100):
    a, cause, n = m.est_alerte(etat, h, 1000, None, 0.0, p)
    etat = {"alert": a, "nb_consecutifs_seuil": n}
    resultats.append(a)
verifie("persistance 3 : alerte à la 3e mesure seulement", resultats == [False, False, True])

# 3. Hystérésis
p = dict(m.PARAMETRES_DEFAUT, hysteresis_pct=20)
verifie("hystérésis 20 % : reste en alerte à 850 mm", m.est_alerte({"alert": True}, 850, 1000, None, None, p)[0])
verifie("hystérésis 20 % : sort d'alerte à 750 mm", not m.est_alerte({"alert": True}, 750, 1000, None, None, p)[0])

# 4. Montée rapide au-dessus du seuil
p = dict(m.PARAMETRES_DEFAUT, persistance_mesures=3)
a, cause, _ = m.est_alerte({"alert": False, "nb_consecutifs_seuil": 0}, 1050, 1000, None, 300.0, p)
verifie("300 mm/h > 200 : alerte immédiate, cause montee_rapide", a and cause == "montee_rapide")
a, _, _ = m.est_alerte({"alert": False, "nb_consecutifs_seuil": 0}, 1050, 1000, None, 100.0, p)
verifie("100 mm/h < 200 : pas d'alerte avant la persistance", not a)
p0 = dict(p, montee_rapide_mm_h=0)
verifie("montée rapide désactivée (0)", not m.est_alerte({"alert": False}, 1050, 1000, None, 900.0, p0)[0])

# 5. Anticipation (temps avant seuil)
verifie("seuil atteint dans 10 min ≤ 15 : alerte anticipée",
        m.est_alerte({"alert": False}, 900, 1000, 10.0, 600.0, m.PARAMETRES_DEFAUT)[0])
p0 = dict(m.PARAMETRES_DEFAUT, temps_avant_seuil_min=0)
verifie("anticipation désactivée (0)", not m.est_alerte({"alert": False}, 900, 1000, 10.0, 600.0, p0)[0])

# 6. Saut aberrant
t, v, tend = m.calculer_temps_avant_depassement(trame(2500, 5), trame(500, 0), 3000, 1500)
verifie("saut de 2 m > 1,5 m : ni vitesse ni anticipation", t is None and v is None)
t, v, tend = m.calculer_temps_avant_depassement(trame(600, 30), trame(500, 0), 3000, 1500)
verifie("montée normale : vitesse 200 mm/h", v == 200.0 and tend == "montante")

print("\n" + ("Tous les tests passent." if echecs == 0 else f"{echecs} test(s) en échec."))
sys.exit(1 if echecs else 0)
