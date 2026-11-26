import json
import time
import subprocess
import threading
from pathlib import Path
import paho.mqtt.client as mqtt

# ==============================================================================
# CONFIGURATION
# ==============================================================================

RACINE_DEPOT = Path(__file__).resolve().parents[2]
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_ALERTES = "pce92/alertes/+"

# Liste des 9 scénarios de l'injecteur
SCENARIOS_LISTE = [
    "normal",
    "montee",
    "montee_rapide",
    "pic",
    "trame_perdue",
    "doublon",
    "capteur_muet",
    "mesure_invalide",
    "batterie_faible"
]

# Structure pour stocker les résultats par scénario
resultats_tests = {scen: [] for scen in SCENARIOS_LISTE}
scen_actuel = None
verrou_tests = threading.Lock()

# Fichier de sortie
RESULTATS_TXT_PATH = RACINE_DEPOT / "plateforme" / "config" / "résultats_AL7.txt"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[TEST AL7] Connecté au broker MQTT {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPIC_ALERTES)
        print(f"[TEST AL7] En écoute sur le topic : {TOPIC_ALERTES}\n")
    else:
        print(f"[TEST AL7] Échec de connexion au broker (code {rc})")


def on_message(client, userdata, msg):
    global scen_actuel
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        
        # Récupération complète de toutes les données du JSON d'alerte
        node_id = payload.get("node_id")
        site = payload.get("site")
        etat = payload.get("etat", "").upper()
        cause = payload.get("cause")
        hauteur = payload.get("hauteur_mm")
        seuil = payload.get("seuil_mm")
        tendance = payload.get("tendance")
        vitesse = payload.get("vitesse_mm_h")
        temps_dep = payload.get("temps_avant_depassement_min")
        received_at = payload.get("received_at")
        
        # Formatage complet de la ligne avec tous les champs
        ligne_resume = (
            f"[{etat}] Site:{site} (Node {node_id}) | "
            f"Hauteur:{hauteur}mm / Seuil:{seuil}mm | "
            f"Tendance:{tendance} | Vitesse:{vitesse}mm/h | "
            f"Temps avant dépassement:{temps_dep}min | "
            f"Cause:{cause} | Reçu le:{received_at}"
        )
        
        print(f"  -> Alerte captée (Scénario en cours: {scen_actuel}) : {ligne_resume}")
        
        with verrou_tests:
            if scen_actuel:
                resultats_tests[scen_actuel].append(ligne_resume)

    except json.JSONDecodeError:
        print(f"[ERREUR] Message non JSON reçu sur {msg.topic}: {msg.payload}")
    except Exception as e:
        print(f"[ERREUR] Traitement du message d'alerte impossible : {e}")


def ecrire_rapport():
    """Écrit tous les résultats cumulés dans plateforme/config/résultats_AL7.txt avec toutes les données"""
    RESULTATS_TXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(RESULTATS_TXT_PATH, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write("       RAPPORT DE VALIDATION DES SCÉNARIOS AL7\n")
        f.write("==================================================\n\n")
        
        for scen, alertes in resultats_tests.items():
            f.write(f"Scénario : {scen.upper()}\n")
            f.write("-" * 50 + "\n")
            if alertes:
                for alt in alertes:
                    f.write(f"  * {alt}\n")
            else:
                f.write("  * Aucune alerte générée (normal selon le scénario).\n")
            f.write("\n")
            
    print(f"\n[TEST AL7] Rapport complet sauvegardé avec succès dans : {RESULTATS_TXT_PATH}")


def lancer_campagne_tests():
    global scen_actuel, scenarios_index
    time.sleep(2)  # Laisse le temps au client MQTT de bien s'initialiser
    
    print("==================================================")
    print(" DÉMARRAGE DE LA CAMPAGNE AUTOMATISÉE DES SCÉNARIOS")
    print("==================================================\n")
    
    for i, scenario in enumerate(SCENARIOS_LISTE, start=1):
        with verrou_tests:
            scen_actuel = scenario
            
        print(f"\n>>> Exécution du scénario [{i}/9] : '{scenario}' avec --node-id {i}")
        
        cmd = ["py", "-m", "injecteur", "--scenario", scenario, "--node-id", str(i), "--vitesse", "900"]
        
        try:
            chemin_simulateur = RACINE_DEPOT / "plateforme" / "injecteur"
            result = subprocess.run(cmd, cwd=chemin_simulateur, capture_output=True, text=True, timeout=15)
            
            if result.returncode != 0:
                print(f"[AVERTISSEMENT] L'injecteur a renvoyé une erreur pour {scenario}:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"[INFO] Scénario {scenario} exécuté (timeout atteint pour laisser le temps aux threads).")
        except Exception as e:
            print(f"[ERREUR] Impossible de lancer l'injecteur pour {scenario} : {e}")
            
        time.sleep(4)

    print("\n==================================================")
    print(" FIN DE LA CAMPAGNE DE TESTS - ÉCRITURE DU RAPPORT")
    print("==================================================")
    ecrire_rapport()


if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        lancer_campagne_tests()
        client.loop_stop()
        client.disconnect()
        
    except KeyboardInterrupt:
        print("\n[TEST AL7] Interruption utilisateur. Arrêt du script.")
        client.loop_stop()
        client.disconnect()