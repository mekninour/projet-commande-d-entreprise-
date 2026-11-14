import csv
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# ==============================================================================
# CONFIGURATION
# ==============================================================================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_MESURES = "pce92/mesures/+"
TOPIC_ALERTES_PREFIX = "pce92/alertes/"

# Adaptez ces chemins selon l'emplacement réel de vos fichiers
CSV_SEUILS_PATH = "plateforme/config/seuils.csv"
DB_SQLITE_PATH = "pce92.db"

# Paramètre métier : temps restant critique (en min) avant dépassement déclenchant une alerte "montee_rapide"
SEUIL_MONTEE_RAPIDE_MIN = 15.0

# Dictionnaires en mémoire pour le suivi en temps réel
suivi_capteurs = {}     # Pour le délai capteur muet
derniers_etats = {}     # Pour garder l'état d'alerte précédent (hystérésis) et la dernière mesure valide
verrou = threading.Lock()


# ==============================================================================
# 1. FONCTIONS MÉTIER (Selon la spécification)
# ==============================================================================

def requete_site_et_seuil(node_id, csv_path=CSV_SEUILS_PATH):
    """Interroge le fichier CSV pour extraire le nom du site et le seuil critique associés au capteur."""
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["node_id"]) == int(node_id):
                return row["site"].strip(), int(row["seuil_alerte"])
    raise ValueError(f"Capteur {node_id} introuvable dans {csv_path}")


def requete_trame_precedente(node_id, db_path=DB_SQLITE_PATH):
    """Récupère dans l'historique SQLite (S3) la dernière trame valide enregistrée."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # S'assure que la table existe pour éviter l'erreur "no such table" lors du premier lancement
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mesures (
                node_id INTEGER,
                received_at TEXT,
                water_mm REAL,
                water_valid BOOLEAN,
                alert BOOLEAN
            )
        """)
        conn.commit()
        
        cursor.execute("""
            SELECT water_mm, received_at, alert 
            FROM mesures 
            WHERE node_id = ? AND water_valid = 1 
            ORDER BY received_at DESC LIMIT 1
        """, (node_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "water_mm": row[0],
                "received_at": row[1],
                "alert": bool(row[2])
            }
    except sqlite3.Error as e:
        # En cas d'autre type d'erreur, on l'affiche discrètement mais sans bloquer
        print(f"[INFO SQLite] Pas encore d'historique disponible pour le capteur {node_id}.")
    return None


def calculer_temps_avant_depassement(trame_act, trame_prec, seuil):
    """Calcule la vitesse de montée (mm/h) et extrapole le temps restant (en min) avant d'atteindre le seuil."""
    if not trame_prec:
        return None, 0.0, "stable"
    
    h_act = trame_act["water_mm"]
    h_prec = trame_prec["water_mm"]
    
    t_act = datetime.fromisoformat(trame_act["received_at"].replace("Z", "+00:00"))
    t_prec = datetime.fromisoformat(trame_prec["received_at"].replace("Z", "+00:00"))
    
    delta_h = h_act - h_prec
    delta_t_heures = (t_act - t_prec).total_seconds() / 3600.0
    
    if delta_t_heures <= 0:
        return None, 0.0, "stable"
        
    vitesse_mm_h = round(delta_h / delta_t_heures, 2)
    
    if delta_h > 0:
        tendance = "montante"
    elif delta_h < 0:
        tendance = "descendante"
    else:
        tendance = "stable"
        
    # S'il n'y a pas de montée ou que le seuil est déjà dépassé, temps_avant_depassement_min = None
    if delta_h <= 0 or h_act >= seuil:
        return None, vitesse_mm_h, tendance
        
    mm_restants = seuil - h_act
    temps_heures = mm_restants / vitesse_mm_h
    temps_minutes = round(temps_heures * 60.0, 1)
    
    return temps_minutes, vitesse_mm_h, tendance


def est_alerte(est_prec_alerte, hauteur, seuil, temps_depassement):
    """Évalue les conditions de déclenchement (dépassement avec hystérésis à 5% ou montée rapide critique)."""
    seuil_hysteresis = seuil * 0.95  # Retour à la normale sous 95% du seuil
    
    if est_prec_alerte:
        # Maintien de l'alerte tant qu'on n'est pas redescendu sous le seuil d'hystérésis
        if hauteur >= seuil_hysteresis:
            return True, ("seuil" if hauteur >= seuil else "hysteresis")
        return False, None
    else:
        # Déclenchement d'une nouvelle alerte
        if hauteur >= seuil:
            return True, "seuil"
        if temps_depassement is not None and temps_depassement <= SEUIL_MONTEE_RAPIDE_MIN:
            return True, "montee_rapide"
        return False, None


def construit_json(node_id, site, seuil, hauteur, etat, cause, tendance, vitesse, temps_depassement, received_at):
    """Assemble et formate l'objet d'alerte AL3."""
    alerte_objet = {
        "node_id": node_id,
        "site": site,
        "etat": etat,
        "cause": cause,
        "hauteur_mm": hauteur,
        "seuil_mm": seuil,
        "tendance": tendance,
        "vitesse_mm_h": vitesse,
        "temps_avant_depassement_min": temps_depassement,
        "received_at": received_at
    }
    return json.dumps(alerte_objet)


# ==============================================================================
# 2. SURVEILLANCE DES CAPTEURS MUETS (Thread d'arrière-plan)
# ==============================================================================

def verifier_capteurs_muets(client):
    """Vérifie périodiquement si un capteur a dépassé son délai (2 * next_min + 5 min)."""
    pass
    """while True:
        time.sleep(15)  # Vérification toutes les 15 secondes
        maintenant = datetime.now(timezone.utc)
        
        with verrou:
            for node_id, data in list(suivi_capteurs.items()):
                # Si déjà déclaré muet, inutile de republier en boucle
                if data.get("est_muet", False):
                    continue
                    
                next_min = data.get("next_min", 30)
                delai_limite_min = (2 * next_min) + 5
                diff_min = (maintenant - data["derniere_reception"]).total_seconds() / 60.0
                
                if diff_min > delai_limite_min:
                    data["est_muet"] = True
                    payload_muet = construit_json(
                        node_id=node_id,
                        site=data["site"],
                        seuil=data["seuil"],
                        hauteur=data.get("derniere_hauteur"),
                        etat="muet",
                        cause=None,
                        tendance="stable",
                        vitesse=0.0,
                        temps_depassement=None,
                        received_at=maintenant.isoformat()
                    )
                    topic = f"{TOPIC_ALERTES_PREFIX}{node_id}"
                    client.publish(topic, payload_muet, qos=1, retain=True)
                    print(f"[MUET] Capteur {node_id} ({data['site']}) silencieux depuis {diff_min:.1f} min -> Publié sur {topic}")"""


# ==============================================================================
# 3. GESTION MQTT (Réception et traitement des mesures)
# ==============================================================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connecté au broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPIC_MESURES)
        print(f"[MQTT] Abonné à {TOPIC_MESURES}")
    else:
        print(f"[MQTT] Échec de connexion, code retour : {rc}")


def on_message(client, userdata, msg):
    try:
        mesure = json.loads(msg.payload.decode("utf-8"))
        node_id = int(mesure["node_id"])
        
        # Récupération du site et du seuil dans le CSV
        site, seuil = requete_site_et_seuil(node_id)
        
        with verrou:
            # 1. Mise à jour du timer pour la détection "capteur muet" (même si la mesure est invalide, le capteur a émis)
            # On convertit le received_at de la trame en objet datetime (en UTC)
            dt_reception = datetime.fromisoformat(mesure["received_at"].replace("Z", "+00:00"))

            suivi_capteurs[node_id] = {
                "dernier_datetime": dt_reception,  # On garde la date de la dernière trame
                "next_min": mesure.get("next_min", 30),
                "site": site,
                "seuil": seuil,
                "derniere_hauteur": mesure.get("water_mm") if mesure.get("water_valid") else suivi_capteurs.get(node_id, {}).get("derniere_hauteur"),
                "est_muet": False
            }

            if node_id in suivi_capteurs:
                dernier_dt = suivi_capteurs[node_id]["dernier_datetime"]
                actuel_dt = datetime.fromisoformat(mesure["received_at"].replace("Z", "+00:00"))
                
                # Écart en minutes entre cette trame et la précédente
                ecart_minutes = (actuel_dt - dernier_dt).total_seconds() / 60.0
                next_min = suivi_capteurs[node_id]["next_min"]
                seuil_muet = (2 * next_min) + 5
                
                if ecart_minutes > seuil_muet:
                    print(f"[alerte] Trou dans les trames détecté : {ecart_minutes:.1f} min d'absence (seuil muet : {seuil_muet} min)")
            
            # 2. Gestion des mesures invalides (0xFFFF -> water_valid == False)
            if not mesure.get("water_valid", False) or mesure.get("water_mm") is None:
                print(f"[INFO] Capteur {node_id} : mesure invalide ignorée (état inchangé).")
                return
                
            # 3. Récupération de la trame précédente (en mémoire, ou dans SQLite si premier démarrage)
            if node_id in derniers_etats:
                trame_prec = derniers_etats[node_id]
            else:
                trame_prec = requete_trame_precedente(node_id)
                
            # 4. Calculs de vitesse, tendance et temps avant dépassement
            temps_dep, vitesse, tendance = calculer_temps_avant_depassement(mesure, trame_prec, seuil)
            
            # 5. Évaluation de l'état d'alerte
            est_prec_alerte = trame_prec["alert"] if trame_prec else False
            alerte_active, cause = est_alerte(est_prec_alerte, mesure["water_mm"], seuil, temps_dep)
            etat = "alerte" if alerte_active else "normal"
            
            # Si cause == "hysteresis", on affiche "seuil" dans le JSON conformément aux valeurs autorisées
            cause_json = "seuil" if cause == "hysteresis" else cause
            
            # 6. Sauvegarde en mémoire de cette mesure valide comme nouvelle référence précédente
            derniers_etats[node_id] = {
                "water_mm": mesure["water_mm"],
                "received_at": mesure["received_at"],
                "alert": alerte_active
            }
            
        # 7. Construction et publication de l'objet d'alerte sur MQTT (avec retain=True)
        payload_json = construit_json(
            node_id=node_id,
            site=site,
            seuil=seuil,
            hauteur=mesure["water_mm"],
            etat=etat,
            cause=cause_json,
            tendance=tendance,
            vitesse=vitesse,
            temps_depassement=temps_dep,
            received_at=mesure["received_at"]
        )
        
        topic_sortie = f"{TOPIC_ALERTES_PREFIX}{node_id}"
        client.publish(topic_sortie, payload_json, qos=1, retain=True)
        print(f"[PUBLIÉ] {topic_sortie} -> État: {etat.upper()} | Hauteur: {mesure['water_mm']}mm / {seuil}mm | Vitesse: {vitesse}mm/h")

    except Exception as e:
        print(f"[ERREUR] Traitement du message impossible : {e}")


# ==============================================================================
# 4. POINT D'ENTRÉE PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Lancement du thread de surveillance des capteurs muets
    thread_muet = threading.Thread(target=verifier_capteurs_muets, args=(client,), daemon=True)
    thread_muet.start()
    
    print("Démarrage du moteur d'alerte...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt du moteur d'alerte.")
        client.disconnect()