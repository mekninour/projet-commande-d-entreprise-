"""PCE 92 – S5 – Injecteur de trames de test (contrat v1.2, V1).

Simule la réception de trames capteur et les publie dans MQTT, pour tester la
plateforme (Node-RED, stockage, alertes, tableaux de bord) sans matériel.

Deux formats de publication :
  brut       (par défaut) ce que publiera le récepteur LoRa point à point en V1 :
             la trame en hexadécimal + l'heure de réception + la qualité du signal.
             Topic : pce92/uplink
  chirpstack l'ancien format ChirpStack v4 (event/up), décodé par le codec S1.
             Gardé au cas où la chaîne repasse en LoRaWAN.

Exemples :
  python injecteur.py --liste
  python injecteur.py --scenario montee
  python injecteur.py --scenario pic --apercu
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
TOPIC_BRUT = "pce92/uplink"


# ---------------------------------------------------------------------------
# 1. Fabriquer la trame de 12 octets (contrat v1.2)
# ---------------------------------------------------------------------------
def volts_vers_5mv(batt_v):
    """Tension en V -> octet batt_5mv (0xFF si inconnue)."""
    if batt_v is None:
        return 255
    return min(max(round((batt_v - 2.50) / 0.005), 0), 254)


def encoder_trame(node_id, water_mm, batt_5mv, seq, alert, next_min):
    """Encode une trame V1 (big-endian). water_mm None = mesure invalide (0xFFFF)."""
    water = 65535 if water_mm is None else min(water_mm, 65534)
    return (
        node_id.to_bytes(2, "big")
        + water.to_bytes(2, "big")
        + batt_5mv.to_bytes(1, "big")
        + (seq % 65536).to_bytes(2, "big")
        + (1 if alert else 0).to_bytes(1, "big")
        + next_min.to_bytes(1, "big")
        + bytes(3)
    )


# ---------------------------------------------------------------------------
# 2. Décoder avec le codec S1 (format chirpstack uniquement)
# ---------------------------------------------------------------------------
SCRIPT_NODE = """
const { decodeUplink } = require(process.argv[1]);
let entree = "";
process.stdin.on("data", (d) => (entree += d)).on("end", () => {
  const trames = JSON.parse(entree);
  process.stdout.write(JSON.stringify(trames.map((b) => decodeUplink({ bytes: b }))));
});
"""


def decoder_avec_codec(liste_octets):
    """liste d'octets -> liste des résultats de decodeUplink (codec S1, via Node.js)."""
    try:
        res = subprocess.run(
            ["node", "-e", SCRIPT_NODE, str(CODEC)],
            input=json.dumps([list(o) for o in liste_octets]),
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except FileNotFoundError:
        sys.exit("Erreur : Node.js est introuvable (commande « node »). Installe-le ou vérifie le PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Erreur du codec ({CODEC}) :\n{e.stderr}")
    return json.loads(res.stdout)


# ---------------------------------------------------------------------------
# 3. Construire le message
# ---------------------------------------------------------------------------
def message_brut(octets, recu_a, rng):
    """Format du récepteur LoRa point à point (V1)."""
    return {
        "received_at": recu_a,
        "payload_hex": octets.hex().upper(),
        "rssi": rng.randint(-120, -70),
        "snr": round(rng.uniform(-10, 10), 1),
        "source": "injecteur",
    }


def message_chirpstack(args, octets, recu_a, decodage, rng):
    """Format event/up de ChirpStack v4 (si la chaîne repasse en LoRaWAN)."""
    message = {
        "deduplicationId": str(uuid.uuid4()),
        "time": recu_a,
        "deviceInfo": {"applicationName": "pce92-crues", "deviceName": "emulateur-esp32-01", "devEui": args.dev_eui},
        "fPort": 1,
        "data": base64.b64encode(octets).decode(),
        "rxInfo": [{"rssi": rng.randint(-120, -70), "snr": round(rng.uniform(-10, 10), 1), "time": recu_a}],
    }
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
                     "Vérifie que Docker Desktop (Mosquitto) tourne.")
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
    p = argparse.ArgumentParser(description="Injecteur de trames de test (tâche S5, contrat v1.2).")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), help="scénario à rejouer")
    p.add_argument("--liste", action="store_true", help="affiche les scénarios disponibles")
    p.add_argument("--format", choices=["brut", "chirpstack"], default="brut",
                   help="brut = récepteur LoRa point à point (V1, défaut) ; chirpstack = ancien format LoRaWAN")
    p.add_argument("--hote", default="localhost", help="broker MQTT (défaut : localhost)")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--node-id", type=int, default=3, help="node_id écrit dans la trame (identifie le site)")
    p.add_argument("--seq-depart", type=int, default=1, help="premier numéro de trame")
    p.add_argument("--seuil", type=int, default=300, help="seuil d'alerte du nœud, en mm (contrat : 300)")
    p.add_argument("--periode", type=int, default=30,
                   help="minutes entre deux trames, envoyées dans next_min (fréquence fixe en V1)")
    p.add_argument("--vitesse", type=float, default=900,
                   help="accélération du temps (900 = 30 min simulées en 2 s ; 1 = temps réel)")
    p.add_argument("--app-id", default="00000000-0000-0000-0000-000000000000", help="format chirpstack uniquement")
    p.add_argument("--dev-eui", default="0000000000000001", help="format chirpstack uniquement")
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
    intervalle_s = args.periode * 60

    # Heures de réception simulées, espacées de --periode. En temps accéléré, le scénario
    # se termine « maintenant » (aucune date dans le futur) ; en temps réel, il démarre maintenant.
    maintenant = datetime.now(timezone.utc)
    debut = maintenant if args.vitesse == 1 else maintenant - timedelta(seconds=(len(etapes) - 1) * intervalle_s)

    trames = []
    for i, e in enumerate(etapes):
        alerte = e["water_mm"] is not None and e["water_mm"] >= args.seuil
        octets = encoder_trame(args.node_id, e["water_mm"], volts_vers_5mv(e["batt_v"]),
                               args.seq_depart + i, alerte, args.periode)
        recu_a = (debut + timedelta(seconds=i * intervalle_s)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        trames.append((octets, recu_a, alerte))

    decodages = decoder_avec_codec([o for o, _, _ in trames]) if args.format == "chirpstack" else [{}] * len(trames)
    topic = TOPIC_BRUT if args.format == "brut" else f"application/{args.app_id}/device/{args.dev_eui}/event/up"
    pause = intervalle_s / args.vitesse
    publieur = None if args.apercu else Publieur(args.hote, args.port)
    print(f"Scénario « {args.scenario} » : {len(etapes)} trames, 1 toutes les {pause:.1f} s, topic {topic}\n")

    try:
        for i, (e, (octets, recu_a, alerte), dec) in enumerate(zip(etapes, trames, decodages)):
            niveau = "invalide" if e["water_mm"] is None else f"{e['water_mm']} mm"
            batt = "inconnue" if e["batt_v"] is None else f"{e['batt_v']:.2f} V"
            ligne = (f"[{i + 1:>2}/{len(etapes)}] seq={args.seq_depart + i:<4} niveau={niveau:<9} "
                     f"batt={batt:<8} {'ALERTE' if alerte else ''}")

            if e["perdue"]:
                print(ligne + "  -> PERDUE, non publiée")
            else:
                envois = 2 if e["doublon"] else 1
                for _ in range(envois):
                    message = (message_brut(octets, recu_a, rng) if args.format == "brut"
                               else message_chirpstack(args, octets, recu_a, dec, rng))
                    if publieur:
                        publieur.publier(topic, message)
                    else:
                        print(json.dumps(message, ensure_ascii=False, indent=2))
                print(ligne + ("  -> publiée 2 fois (doublon)" if envois == 2 else "  -> publiée"))

            if i < len(etapes) - 1 and publieur:
                time.sleep(pause)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        if publieur:
            publieur.fermer()

    if args.scenario == "capteur_muet":
        print(f"\nSilence simulé : la trame suivante était attendue dans {args.periode} min, elle n'arrivera pas.")


if __name__ == "__main__":
    main()
