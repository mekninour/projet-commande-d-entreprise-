"""Tests de la détection des capteurs muets et de la reprise au démarrage, sans broker MQTT.

Lancer depuis la racine du dépôt : python3 plateforme/config/test_capteurs_muets.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone

# Le moteur importe paho-mqtt ; ces tests n'en ont pas besoin.
if "paho" not in sys.modules:
    paho = types.ModuleType("paho"); paho.mqtt = types.ModuleType("paho.mqtt")
    paho.mqtt.client = types.ModuleType("paho.mqtt.client")
    sys.modules.update({"paho": paho, "paho.mqtt": paho.mqtt, "paho.mqtt.client": paho.mqtt.client})

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import moteur_alerte as m  # noqa: E402

echecs = 0


def verifie(nom, condition):
    global echecs
    print(("OK    " if condition else "ECHEC ") + nom)
    if not condition:
        echecs += 1


class ClientFactice:
    """Remplace le client MQTT : garde les messages publiés."""
    def __init__(self):
        self.publies = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.publies.append((topic, json.loads(payload), retain))

    def vider(self):
        p, self.publies = self.publies, []
        return p


class Msg:
    def __init__(self, mesure):
        self.payload = json.dumps(mesure).encode("utf-8")


def heure(minute):
    return datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)


def iso(minute):
    return heure(minute).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def mesure(node_id, seq, h, minute, next_min=30):
    return {"node_id": node_id, "seq": seq, "water_mm": h, "water_valid": h is not None,
            "next_min": next_min, "received_at": iso(minute)}


def remise_a_zero():
    m.suivi_capteurs.clear()
    m.derniers_etats.clear()


tmp = tempfile.mkdtemp()
json_path = os.path.join(tmp, "parametres_alerte.json")
csv_path = os.path.join(tmp, "seuils.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("node_id,site,seuil_alerte,muet_facteur_next_min\n1,SITE-1,1000,\n2,SITE-2,1000,3\n")

# 1. Échéance = 2 × next_min + 5 min, réglable
p = m.charger_parametres(None, json_path)
suivi = {"dernier_datetime": heure(0), "next_min": 30}
verifie("défaut : échéance à 2 × 30 + 5 = 65 min", m.echeance_capteur(suivi, p) == heure(65))
verifie("next_min inconnu (0xFF) : 30 min par défaut",
        m.echeance_capteur({"dernier_datetime": heure(0), "next_min": None}, p) == heure(65))
verifie("next_min 15 (vigilance) : échéance à 35 min",
        m.echeance_capteur({"dernier_datetime": heure(0), "next_min": 15}, p) == heure(35))
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"muet_marge_min": 0}, f)
verifie("JSON : marge 0 → échéance à 60 min",
        m.echeance_capteur(suivi, m.charger_parametres(None, json_path)) == heure(60))
os.remove(json_path)
_, _, p2 = m.params_capteur(2, csv_path, json_path)
verifie("CSV : facteur 3 pour le capteur 2 → échéance à 95 min", m.echeance_capteur(suivi, p2) == heure(95))

# 2. Contrôle : objet AL3 « muet » publié une seule fois
remise_a_zero()
client = ClientFactice()
m.suivi_capteurs[1] = {"dernier_datetime": heure(0), "received_at": iso(0), "next_min": 30,
                       "site": "SITE-1", "seuil": 1000, "derniere_hauteur": 420, "est_muet": False}
verifie("64 min sans trame : pas encore muet",
        m.controler_capteurs_muets(client, heure(64), csv_path, json_path) == [] and not client.publies)
m.controler_capteurs_muets(client, heure(66), csv_path, json_path)
publies = client.vider()
verifie("66 min sans trame : un objet publié", len(publies) == 1)
topic, objet, retain = publies[0]
verifie("objet muet : topic pce92/alertes/1, retenu", topic == "pce92/alertes/1" and retain)
verifie("objet muet : etat muet, cause capteur_muet", objet["etat"] == "muet" and objet["cause"] == "capteur_muet")
verifie("objet muet : dernier niveau et heure de la dernière trame",
        objet["hauteur_mm"] == 420 and objet["received_at"] == iso(0) and objet["seuil_mm"] == 1000)
verifie("objet muet : mêmes champs que l'objet AL3 habituel",
        set(objet) == set(json.loads(m.construit_json(1, "", 0, 0, "", "", "", 0, 0, "")).keys()))
m.controler_capteurs_muets(client, heure(67), csv_path, json_path)
m.controler_capteurs_muets(client, heure(500), csv_path, json_path)
verifie("contrôles suivants : rien de plus (une seule publication)", not client.publies)

# 3. Retour du capteur : un objet AL3 « retour » une seule fois, puis l'objet habituel
m.maintenant = lambda: heure(200)
m.derniers_etats[1] = {"seq": 10, "water_mm": 1100, "received_at": iso(0), "alert": True, "nb_consecutifs_seuil": 2}
m.on_message(client, None, Msg(mesure(1, 11, 1050, 200)))
publies = client.vider()
verifie("retour : deux objets publiés (retour puis mesure)", len(publies) == 2)
verifie("retour : cause retour_capteur, état d'avant le silence (alerte)",
        publies[0][1]["cause"] == "retour_capteur" and publies[0][1]["etat"] == "alerte")
verifie("retour : puis l'objet habituel de la mesure", publies[1][1]["cause"] == "seuil" and publies[1][1]["hauteur_mm"] == 1050)
verifie("retour : le capteur n'est plus muet", not m.suivi_capteurs[1]["est_muet"])
m.on_message(client, None, Msg(mesure(1, 12, 1050, 230)))
verifie("trame suivante : pas de nouvel objet retour",
        [o["cause"] for _, o, _ in client.vider()] == ["seuil"])
verifie("nouvelle échéance depuis la dernière arrivée", not m.controler_capteurs_muets(client, heure(264), csv_path, json_path))

# 4. Retour avec une mesure invalide (0xFFFF) : retour publié, pas de verdict
remise_a_zero()
m.suivi_capteurs[1] = {"dernier_datetime": heure(0), "received_at": iso(0), "next_min": 30,
                       "site": "SITE-1", "seuil": 1000, "derniere_hauteur": 420, "est_muet": True}
m.derniers_etats[1] = {"seq": 10, "water_mm": 420, "received_at": iso(0), "alert": False, "nb_consecutifs_seuil": 0}
m.on_message(client, None, Msg(mesure(1, 11, None, 200)))
publies = client.vider()
verifie("mesure invalide : seul l'objet retour, état normal",
        len(publies) == 1 and publies[0][1]["cause"] == "retour_capteur" and publies[0][1]["etat"] == "normal")
verifie("mesure invalide : dernier niveau valide gardé", m.suivi_capteurs[1]["derniere_hauteur"] == 420)

# 5. Trame rejouée avec une heure passée (injecteur) : l'échéance part de l'arrivée
remise_a_zero()
m.maintenant = lambda: heure(1000)
m.derniers_etats[1] = {"seq": 1, "water_mm": 400, "received_at": iso(0), "alert": False, "nb_consecutifs_seuil": 0}
m.on_message(client, None, Msg(mesure(1, 2, 400, 30)))   # received_at 10 h 30, arrivée 26 h 40
client.vider()
verifie("trame à heure passée : pas muet juste après son arrivée",
        not m.controler_capteurs_muets(client, heure(1001), csv_path, json_path))

# 6. Démarrage : échéances reprises depuis la base
db_path = os.path.join(tmp, "pce92.db")
conn = sqlite3.connect(db_path)
with open(os.path.join(ICI, "..", "flows", "s3_schema.sql"), encoding="utf-8") as f:
    conn.executescript(f.read())


def ligne(node_id, minute, h, seq, alert=0, next_min=30):
    conn.execute("INSERT INTO mesures (node_id, received_at, water_mm, water_valid, seq, alert, next_min) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (node_id, iso(minute), h, 1 if h is not None else 0, seq, alert, next_min))


ligne(1, 0, 400, 1); ligne(1, 30, 410, 2); ligne(1, 60, None, 3)           # capteur 1 : dernière trame à 60 min
ligne(2, 0, 400, 1); ligne(2, 90, 400, 2, next_min=15)                    # capteur 2 : dernière trame à 90 min
ligne(7, 90, 400, 1)                                                      # capteur 7 : absent de seuils.csv
conn.commit()
remise_a_zero()
verifie("démarrage : 2 capteurs repris (le 7, inconnu, ignoré)", m.charger_echeances_depuis_base(db_path, csv_path) == 2)
verifie("démarrage : dernière trame et next_min de la base",
        m.suivi_capteurs[1]["received_at"] == iso(60) and m.suivi_capteurs[2]["next_min"] == 15)
verifie("démarrage : dernier niveau valide (pas la trame invalide)", m.suivi_capteurs[1]["derniere_hauteur"] == 410)
muets = m.controler_capteurs_muets(client, heure(126), csv_path, json_path)
verifie("démarrage : capteur 1 muet à 60 + 65 min, capteur 2 pas encore (3 × 15 + 5)", muets == [1])
verifie("démarrage : capteur 2 muet à 90 + 50 min", m.controler_capteurs_muets(client, heure(141), csv_path, json_path) == [2])
client.vider()
remise_a_zero()
verifie("base absente : rien repris, pas d'erreur",
        m.charger_echeances_depuis_base(os.path.join(tmp, "absente.db"), csv_path) == 0
        and not os.path.exists(os.path.join(tmp, "absente.db")))

# 7. Correction : l'état du moteur au démarrage ne vient plus de la colonne alert (bit du nœud)
p = m.charger_parametres(None, json_path)
ligne(3, 0, 200, 1, alert=1); ligne(3, 30, 250, 2, alert=1)               # bit du nœud à 1, niveau sous 1000
ligne(4, 0, 1100, 1); ligne(4, 30, 1100, 2); ligne(4, 60, 950, 3)       # au-dessus puis zone d'hystérésis, bit à 0
conn.commit()
etat3 = m.reconstruire_etat(3, 1000, p, db_path=db_path)
verifie("bit du nœud à 1 sous le seuil du moteur : pas en alerte", etat3["alert"] is False)
etat4 = m.reconstruire_etat(4, 1000, p, db_path=db_path)
verifie("2 mesures au-dessus puis 950 mm : toujours en alerte (hystérésis), bit du nœud à 0",
        etat4["alert"] is True and etat4["seq"] == 3)
etat4b = m.reconstruire_etat(4, 1000, p, avant=iso(30), db_path=db_path)
verifie("avant = mesure en cours : elle n'est pas comptée deux fois",
        etat4b["received_at"] == iso(0) and etat4b["nb_consecutifs_seuil"] == 1 and not etat4b["alert"])
verifie("capteur sans historique : None", m.reconstruire_etat(9, 1000, p, db_path=db_path) is None)
conn.close()

print("\n" + ("Tous les tests passent." if echecs == 0 else f"{echecs} test(s) en échec."))
sys.exit(1 if echecs else 0)
