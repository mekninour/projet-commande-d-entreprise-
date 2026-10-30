"""PCE 92 – S5 – Injecteur de trames de test.

Se fait passer pour ChirpStack : publie dans MQTT des messages « event/up »
au même format que ChirpStack v4, pour tester la plateforme (Node-RED,
stockage, alertes, dashboards) sans ESP32 ni passerelle.

Pour chaque étape du scénario :
  1. fabrique la trame de 12 octets (contrat d'interface) ;
  2. la décode avec le codec S1 (trame/decodeur/codec.js, via Node.js),
     exactement comme le ferait ChirpStack ;
  3. l'emballe dans le JSON event/up et la publie sur
     application/<app_id>/device/<dev_eui>/event/up

Exemples :
  python injecteur.py --liste
  python injecteur.py --scenario montee
  python injecteur.py --scenario pic --vitesse 1800 --apercu
"""

import argparse
import base64
import json
import random
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scenarios import SCENARIOS, generer

RACINE_DEPOT = Path(__file__).resolve().parents[2]
CODEC = RACINE_DEPOT / "trame" / "decodeur" / "codec.js"

# Hypothèses du contrat, identiques à celles du codec S1.
BATT_MV_PAR_UNITE = 20
BIT_ALERTE, BIT_DEFAUT, BIT_ECO = 0x80, 0x40, 0x20


# ---------------------------------------------------------------------------
# 1. Fabriquer la trame de 12 octets
# ---------------------------------------------------------------------------
def encoder_trame(node_id, water_mm, batt_v, seq, alert=False, sensor_fault=False, eco_mode=False):
    """Encode une trame conforme au contrat (big-endian, octets 8-11 à zéro)."""
    batt_cv = round(batt_v * 1000 / BATT_MV_PAR_UNITE)
    status = (BIT_ALERTE if alert else 0) | (BIT_DEFAUT if sensor_fault else 0) | (BIT_ECO if eco_mode else 0)
    return (
        node_id.to_bytes(2, "big")
        + min(water_mm, 65535).to_bytes(2, "big")
        + min(batt_cv, 255).to_bytes(1, "big")
        + (seq % 65536).to_bytes(2, "big")
        + status.to_bytes(1, "big")
        + bytes(4)
    )


# ---------------------------------------------------------------------------
# 2. Décoder avec le codec S1 (le même code que dans ChirpStack)
# ---------------------------------------------------------------------------
SCRIPT_NODE = """
const { decodeUplink } = require(process.argv[1]);
let entree = "";
process.stdin.on("data", (d) => (entree += d)).on("end", () => {
  const trames = JSON.parse(entree);
  const res = trames.map((t) => decodeUplink({ bytes: t.bytes, fPort: 1, recvTime: new Date(t.time) }));
  process.stdout.write(JSON.stringify(res));
});
"""


def decoder_avec_codec(trames):
    """trames = [(octets, horodatage ISO)] -> liste des résultats de decodeUplink."""
    entree = json.dumps([{"bytes": list(o), "time": t} for o, t in trames])
    try:
        res = subprocess.run(
            ["node", "-e", SCRIPT_NODE, str(CODEC)],
            input=entree, capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except FileNotFoundError:
        sys.exit("Erreur : Node.js est introuvable (commande « node »). Installe-le ou vérifie le PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Erreur du codec ({CODEC}) :\n{e.stderr}")
    return json.loads(res.stdout)


# ---------------------------------------------------------------------------
# 3. Construire le message event/up de ChirpStack v4
# ---------------------------------------------------------------------------
def construire_message(args, octets, horodatage, f_cnt, decodage, rng):
    message = {
        "deduplicationId": str(uuid.uuid4()),
        "time": horodatage,
        "deviceInfo": {
            "tenantName": "ChirpStack",
            "applicationId": args.app_id,
            "applicationName": "pce92-crues",
            "deviceProfileName": "PCE92 – Noeud crue EU868",
            "deviceName": args.device_name,
            "devEui": args.dev_eui,
        },
        "devAddr": "01a2b3c4",
        "adr": True,
        "dr": 5,
        "fCnt": f_cnt,
        "fPort": 1,
        "confirmed": False,
        "data": base64.b64encode(octets).decode(),
        "rxInfo": [{
            "gatewayId": args.gateway_id,
            "rssi": rng.randint(-110, -60),
            "snr": round(rng.uniform(-5, 10), 1),
            "time": horodatage,
        }],
        "txInfo": {
            "frequency": rng.choice([868100000, 868300000, 868500000]),
            "modulation": {"lora": {"bandwidth": 125000, "spreadingFactor": 7, "codeRate": "CR_4_5"}},
        },
    }
    # Comme ChirpStack : pas de champ « object » si le codec renvoie une erreur.
    if "data" in decodage:
        message["object"] = decodage["data"]
    return message


# ---------------------------------------------------------------------------
# 4. Publier dans MQTT
# ---------------------------------------------------------------------------
class Publieur:
    def __init__(self, hote, port):
        import paho.mqtt.client as mqtt
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"injecteur-s5-{uuid.uuid4().hex[:6]}")
        try:
            self.client.connect(hote, port)
        except OSError as e:
            sys.exit(f"Erreur : connexion impossible au broker MQTT {hote}:{port} ({e}).\n"
                     "Vérifie que Docker Desktop et ChirpStack (Mosquitto) tournent.")
        self.client.loop_start()

    def publier(self, topic, message):
        self.client.publish(topic, json.dumps(message, ensure_ascii=False), qos=1).wait_for_publish(timeout=5)

    def fermer(self):
        self.client.loop_stop()
        self.client.disconnect()


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def lire_arguments():
    p = argparse.ArgumentParser(description="Injecteur de trames de test au format ChirpStack v4 (tâche S5).")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), help="scénario à rejouer")
    p.add_argument("--liste", action="store_true", help="affiche les scénarios disponibles")
    p.add_argument("--hote", default="localhost", help="broker MQTT (défaut : localhost)")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--app-id", default="00000000-0000-0000-0000-000000000000",
                   help="identifiant de l'application ChirpStack (visible dans l'URL)")
    p.add_argument("--dev-eui", default="0000000000000001", help="DevEUI du capteur simulé")
    p.add_argument("--device-name", default="emulateur-esp32-01")
    p.add_argument("--gateway-id", default="aa555a0000000001")
    p.add_argument("--node-id", type=int, default=3, help="node_id écrit dans la trame (identifie le site)")
    p.add_argument("--seq-depart", type=int, default=1, help="premier numéro de trame")
    p.add_argument("--seuil", type=int, default=2000, help="seuil d'alerte embarqué du nœud, en mm")
    p.add_argument("--intervalle", type=int, default=1800,
                   help="écart simulé entre deux trames, en secondes (contrat : 1800)")
    p.add_argument("--vitesse", type=float, default=900,
                   help="accélération du temps (900 = 30 min simulées en 2 s ; 1 = temps réel)")
    p.add_argument("--apercu", action="store_true", help="affiche les messages sans rien publier")
    return p.parse_args()


def main():
    args = lire_arguments()
    if args.liste or not args.scenario:
        print("Scénarios disponibles :")
        for nom, fonction in sorted(SCENARIOS.items()):
            print(f"  {nom:<16} {fonction.__doc__.strip().splitlines()[0]}")
        return

    rng = random.Random(92)
    etapes = generer(args.scenario, args.seuil)
    # Horodatages simulés, espacés de --intervalle. En temps accéléré, le scénario
    # se termine « maintenant » (aucune date dans le futur) ; en temps réel, il démarre maintenant.
    maintenant = datetime.now(timezone.utc)
    debut = maintenant if args.vitesse == 1 else maintenant - timedelta(seconds=(len(etapes) - 1) * args.intervalle)

    # Trames de 12 octets et heure de réception de chacune.
    trames = []
    for i, e in enumerate(etapes):
        octets = encoder_trame(args.node_id, e["water_mm"], e["batt_v"], args.seq_depart + i,
                               e["alert"], e["sensor_fault"], e["eco_mode"])
        horodatage = (debut + timedelta(seconds=i * args.intervalle)).isoformat(timespec="milliseconds")
        trames.append((octets, horodatage.replace("+00:00", "Z")))
    decodages = decoder_avec_codec(trames)

    topic = f"application/{args.app_id}/device/{args.dev_eui}/event/up"
    pause = args.intervalle / args.vitesse
    publieur = None if args.apercu else Publieur(args.hote, args.port)
    print(f"Scénario « {args.scenario} » : {len(etapes)} trames, 1 toutes les {pause:.1f} s, topic {topic}\n")

    try:
        for i, (e, (octets, horodatage), dec) in enumerate(zip(etapes, trames, decodages)):
            seq = args.seq_depart + i
            etat = "ALERTE" if e["alert"] else ("défaut" if e["sensor_fault"] else "")
            ligne = f"[{i + 1:>2}/{len(etapes)}] seq={seq:<4} water_mm={e['water_mm']:<5} batt={e['batt_v']:.2f} V {etat}"
            for avert in dec.get("warnings", []) + dec.get("errors", []):
                ligne += f"  (codec : {avert})"

            if e["perdue"]:
                print(ligne + "  -> PERDUE, non publiée")
            else:
                message = construire_message(args, octets, horodatage, seq, dec, rng)
                envois = 2 if e["doublon"] else 1
                for _ in range(envois):
                    if publieur:
                        publieur.publier(topic, message)
                    else:
                        print(json.dumps(message, ensure_ascii=False, indent=2))
                    message = dict(message, deduplicationId=str(uuid.uuid4()))
                print(ligne + ("  -> publiée 2 fois (doublon)" if envois == 2 else "  -> publiée"))

            if i < len(etapes) - 1 and publieur:
                time.sleep(pause)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        if publieur:
            publieur.fermer()

    if args.scenario == "capteur_muet":
        print("\nSilence simulé : plus aucune trame ne sera publiée pour ce capteur.")


if __name__ == "__main__":
    main()
