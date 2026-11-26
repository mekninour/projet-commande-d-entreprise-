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

CSV_SEUILS_PATH = "plateforme/config/seuils.csv"
PARAMETRES_PATH = "plateforme/config/parametres_alerte.json"
DB_SQLITE_PATH = "pce92.db"

# Valeurs utilisées si parametres_alerte.json est absent ou incomplet.
# Les vraies valeurs se règlent dans parametres_alerte.json (pour tous les capteurs)
# ou dans une colonne du même nom de seuils.csv (pour un capteur). Voir PARAMETRES.md.
PARAMETRES_DEFAUT = {
    "persistance_mesures": 2,      # mesures consécutives au-dessus du seuil avant l'alerte
    "hysteresis_pct": 10.0,        # sortie d'alerte sous seuil × (1 - hysteresis_pct / 100)
    "temps_avant_seuil_min": 15.0, # alerte anticipée si le seuil sera atteint dans ce délai (0 = désactivé)
    "montee_rapide_mm_h": 200.0,   # au-dessus du seuil, alerte sans attendre la persistance (0 = désactivé)
    "saut_max_mm": 1500,           # écart entre deux mesures jugé impossible : ignoré pour la vitesse (0 = désactivé)
}

# Dictionnaires en mémoire pour le suivi
suivi_capteurs = {}     # Pour le délai capteur muet
derniers_etats = {}     # Pour l'état précédent, le seq, et le compteur consécutif
verrou = threading.Lock()


# ==============================================================================
# 1. FONCTIONS MÉTIER
# ==============================================================================

def requete_site_et_seuil(node_id, csv_path=CSV_SEUILS_PATH):
    """Interroge le fichier CSV pour extraire le nom du site et le seuil critique."""
    site, seuil, _ = requete_capteur(node_id, csv_path)
    return site, seuil


def requete_capteur(node_id, csv_path=CSV_SEUILS_PATH):
    """Lit la ligne du capteur dans seuils.csv : site, seuil et réglages propres au capteur."""
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["node_id"]) == int(node_id):
                propres = {k: v for k, v in row.items()
                           if k in PARAMETRES_DEFAUT and v is not None and str(v).strip() != ""}
                return row["site"].strip(), int(row["seuil_alerte"]), propres
    raise ValueError(f"Capteur {node_id} introuvable dans {csv_path}")


def charger_parametres(propres_capteur=None, json_path=PARAMETRES_PATH):
    """Réglages du moteur : défauts du code < parametres_alerte.json < colonne de seuils.csv.

    Les fichiers sont relus à chaque mesure : une modification s'applique sans redémarrer.
    Une valeur illisible est ignorée (on garde la précédente) et signalée.
    """
    params = dict(PARAMETRES_DEFAUT)
    sources = []
    try:
        with open(json_path, encoding="utf-8") as f:
            sources.append((json_path, json.load(f)))
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        print(f"[CONFIG] {json_path} illisible ({e}) : valeurs par défaut utilisées.")
    if propres_capteur:
        sources.append(("seuils.csv", propres_capteur))
    for origine, valeurs in sources:
        for cle, valeur in valeurs.items():
            if cle not in PARAMETRES_DEFAUT or cle.startswith("_"):
                continue
            try:
                params[cle] = type(PARAMETRES_DEFAUT[cle])(float(valeur))
            except (TypeError, ValueError):
                print(f"[CONFIG] {origine} : valeur « {valeur} » invalide pour {cle}, ignorée.")
    return params


def requete_trame_precedente(node_id, db_path=DB_SQLITE_PATH):
    """Récupère en lecture seule dans l'historique SQLite la dernière trame valide enregistrée."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
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
    except sqlite3.Error:
        print(f"[INFO SQLite] Pas d'historique SQLite disponible pour le capteur {node_id}.")
    return None


def calculer_temps_avant_depassement(trame_act, trame_prec, seuil, saut_max_mm=0):
    """Calcule la vitesse de montée (mm/h) et extrapole le temps restant (en min).

    Un écart supérieur à saut_max_mm entre deux mesures est jugé impossible
    (valeur aberrante du capteur) : il ne donne ni vitesse ni anticipation.
    """
    if not trame_prec:
        return None, 0.0, "stable"
    
    h_act = trame_act["water_mm"]
    h_prec = trame_prec["water_mm"]
    
    t_act = datetime.fromisoformat(trame_act["received_at"].replace("Z", "+00:00"))
    t_prec = datetime.fromisoformat(trame_prec["received_at"].replace("Z", "+00:00"))
    
    delta_h = h_act - h_prec
    if saut_max_mm and abs(delta_h) > saut_max_mm:
        return None, None, "saut_ignore"
    delta_t_heures = (t_act - t_prec).total_seconds() / 3600.0
    
    if delta_t_heures <= 0:
        return None, 0.0, "stable"
        
    vitesse_mm_h = round(delta_h / delta_t_heures, 2)
    tendance = "montante" if delta_h > 0 else ("descendante" if delta_h < 0 else "stable")
        
    if delta_h <= 0 or h_act >= seuil:
        return None, vitesse_mm_h, tendance
        
    mm_restants = seuil - h_act
    temps_heures = mm_restants / vitesse_mm_h
    return round(temps_heures * 60.0, 1), vitesse_mm_h, tendance


def est_alerte(trame_prec, hauteur, seuil, temps_depassement, vitesse=None, params=None):
    """Évalue l'alerte : persistance au-dessus du seuil, hystérésis, montée rapide.

    Tous les réglages viennent de params (voir charger_parametres).
    """
    p = params or PARAMETRES_DEFAUT
    seuil_hysteresis = seuil * (1.0 - p["hysteresis_pct"] / 100.0)
    
    etait_en_alerte = trame_prec["alert"] if trame_prec else False
    nb_consecutifs_precedent = trame_prec.get("nb_consecutifs_seuil", 0) if trame_prec else 0
    
    # 1. Gestion si on était déjà en alerte (Hystérésis)
    if etait_en_alerte:
        if hauteur >= seuil_hysteresis:
            return True, ("seuil" if hauteur >= seuil else "hysteresis"), nb_consecutifs_precedent
        return False, None, 0

    # 2. Gestion en état normal
    if hauteur >= seuil:
        nouveau_nb = nb_consecutifs_precedent + 1
        if nouveau_nb >= max(1, p["persistance_mesures"]):
            return True, "seuil", nouveau_nb
        if p["montee_rapide_mm_h"] > 0 and vitesse is not None and vitesse >= p["montee_rapide_mm_h"]:
            return True, "montee_rapide", nouveau_nb
        else:
            return False, None, nouveau_nb
    else:
        # Remise à zéro du compteur consécutif si on redescend, sauf si montée rapide
        if (p["temps_avant_seuil_min"] > 0 and temps_depassement is not None
                and temps_depassement <= p["temps_avant_seuil_min"]):
            return True, "montee_rapide", 0
        return False, None, 0


def construit_json(node_id, site, seuil, hauteur, etat, cause, tendance, vitesse, temps_depassement, received_at):
    """Assemble et formate l'objet d'alerte AL3."""
    return json.dumps({
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
    })


# ==============================================================================
# 2. SURVEILLANCE DES CAPTEURS MUETS (Thread d'arrière-plan)
# ==============================================================================

def verifier_capteurs_muets(client):
    pass  # Inchangé pour l'instant


# ==============================================================================
# 3. GESTION MQTT
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
        seq_actuel = mesure.get("seq")
        
        site, seuil, propres = requete_capteur(node_id)
        params = charger_parametres(propres)
        
        with verrou:
            # 1. Filtrage des doublons via le seq par rapport à la dernière trame en mémoire
            if node_id in derniers_etats:
                if seq_actuel is not None and derniers_etats[node_id].get("seq") == seq_actuel:
                    print(f"[INFO] Doublon détecté (seq={seq_actuel}) pour le capteur {node_id} -> Ignoré.")
                    return

            dt_reception = datetime.fromisoformat(mesure["received_at"].replace("Z", "+00:00"))

            suivi_capteurs[node_id] = {
                "dernier_datetime": dt_reception,
                "next_min": mesure.get("next_min", 30),
                "site": site,
                "seuil": seuil,
                "derniere_hauteur": mesure.get("water_mm") if mesure.get("water_valid") else suivi_capteurs.get(node_id, {}).get("derniere_hauteur"),
                "est_muet": False
            }
            
            # 2. Gestion des mesures invalides (0xFFFF)
            if not mesure.get("water_valid", False) or mesure.get("water_mm") is None:
                print(f"[INFO] Capteur {node_id} : mesure invalide ignorée.")
                return
                
            # 3. Récupération de la trame précédente (mémoire ou lecture seule SQLite)
            if node_id in derniers_etats:
                trame_prec = derniers_etats[node_id]
            else:
                trame_prec = requete_trame_precedente(node_id)
                
            # 4. Calculs métier
            temps_dep, vitesse, tendance = calculer_temps_avant_depassement(
                mesure, trame_prec, seuil, params["saut_max_mm"])
            
            # 5. Évaluation de l'alerte (persistance, hystérésis, montée rapide : voir parametres_alerte.json)
            alerte_active, cause, nouveau_compteur = est_alerte(
                trame_prec, mesure["water_mm"], seuil, temps_dep, vitesse, params)
            etat = "alerte" if alerte_active else "normal"
            cause_json = "seuil" if cause == "hysteresis" else cause
            
            # 6. Sauvegarde en mémoire de l'état courant
            derniers_etats[node_id] = {
                "seq": seq_actuel,
                "water_mm": mesure["water_mm"],
                "received_at": mesure["received_at"],
                "alert": alerte_active,
                "nb_consecutifs_seuil": nouveau_compteur
            }
            
        # 7. Publication MQTT
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
        print(f"[PUBLIÉ] {topic_sortie} -> État: {etat.upper()} | Hauteur: {mesure['water_mm']}mm / {seuil}mm | Vitesse: {vitesse}mm/h | Seq: {seq_actuel}")

    except Exception as e:
        print(f"[ERREUR] Traitement du message impossible : {e}")


# ==============================================================================
# 4. POINT D'ENTRÉE PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    thread_muet = threading.Thread(target=verifier_capteurs_muets, args=(client,), daemon=True)
    thread_muet.start()
    
    print("Démarrage du moteur d'alerte...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt du moteur d'alerte.")
        client.disconnect()