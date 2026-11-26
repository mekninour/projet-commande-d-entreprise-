import csv
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    # Capteur muet : aucune trame depuis muet_facteur_next_min × next_min + muet_marge_min
    "muet_facteur_next_min": 2.0,  # nombre de trames manquées tolérées
    "muet_marge_min": 5.0,         # marge en plus (retard réseau, dérive de l'horloge du nœud)
    "muet_next_min_defaut": 30.0,  # next_min pris quand la trame ne le donne pas (0xFF)
    "muet_controle_s": 60.0,       # intervalle entre deux contrôles (réglage commun uniquement)
}

# Mesures relues dans la base pour retrouver l'état du moteur au démarrage
FENETRE_RECONSTRUCTION = 50

# Dictionnaires en mémoire pour le suivi
suivi_capteurs = {}     # Pour le délai capteur muet : dernière trame, next_min, est_muet
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


def maintenant():
    """Heure actuelle en UTC (remplacée dans les tests)."""
    return datetime.now(timezone.utc)


def lire_date(texte):
    """Date ISO 8601 de la base ou d'une trame (« Z » accepté), en UTC."""
    d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def ouvrir_base(db_path=DB_SQLITE_PATH):
    """Ouvre la base SQLite de S3 en lecture seule (sans créer de fichier vide si elle manque)."""
    return sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)


def reconstruire_etat(node_id, seuil, params, avant=None, db_path=DB_SQLITE_PATH,
                      fenetre=FENETRE_RECONSTRUCTION):
    """Retrouve l'état du moteur pour un capteur (alerte ou non, compteur de persistance)
    en rejouant ses dernières mesures valides de la base.

    La colonne alert de la base est le bit envoyé par le nœud (son propre seuil), pas l'état
    du moteur : on ne la lit donc pas. avant = received_at de la mesure en cours, pour ne pas
    la compter deux fois si S3 l'a déjà enregistrée.
    """
    requete = "SELECT water_mm, received_at, seq FROM mesures WHERE node_id = ? AND water_valid = 1"
    arguments = [node_id]
    if avant:
        requete += " AND received_at < ?"
        arguments.append(avant)
    requete += " ORDER BY received_at DESC LIMIT ?"
    arguments.append(fenetre)
    try:
        conn = ouvrir_base(db_path)
        try:
            lignes = conn.execute(requete, arguments).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        print(f"[INFO SQLite] Pas d'historique SQLite disponible pour le capteur {node_id}.")
        return None

    etat = None
    for water_mm, received_at, seq in reversed(lignes):
        trame = {"water_mm": water_mm, "received_at": received_at}
        temps_dep, vitesse, _ = calculer_temps_avant_depassement(trame, etat, seuil, params["saut_max_mm"])
        alerte, _, compteur = est_alerte(etat, water_mm, seuil, temps_dep, vitesse, params)
        etat = {"seq": seq, "water_mm": water_mm, "received_at": received_at,
                "alert": alerte, "nb_consecutifs_seuil": compteur}
    return etat


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

def echeance_capteur(suivi, params):
    """Heure limite de la prochaine trame : dernière trame + facteur × next_min + marge."""
    next_min = suivi.get("next_min") or params["muet_next_min_defaut"]
    delai = params["muet_facteur_next_min"] * next_min + params["muet_marge_min"]
    return suivi["dernier_datetime"] + timedelta(minutes=delai)


def params_capteur(node_id, csv_path=CSV_SEUILS_PATH, json_path=PARAMETRES_PATH):
    """Site, seuil et réglages d'un capteur, relus à chaque fois (comme pour les mesures)."""
    site, seuil, propres = requete_capteur(node_id, csv_path)
    return site, seuil, charger_parametres(propres, json_path)


def publier(client, node_id, payload_json):
    topic = f"{TOPIC_ALERTES_PREFIX}{node_id}"
    client.publish(topic, payload_json, qos=1, retain=True)
    return topic


def charger_echeances_depuis_base(db_path=DB_SQLITE_PATH, csv_path=CSV_SEUILS_PATH):
    """Au démarrage : reprend dans la base la dernière trame de chaque capteur, pour que
    les échéances « capteur muet » survivent à un redémarrage du moteur.
    Renvoie le nombre de capteurs repris."""
    try:
        conn = ouvrir_base(db_path)
        try:
            dernieres = conn.execute("""
                SELECT m.node_id, m.received_at, m.next_min
                FROM mesures m
                WHERE m.received_at = (SELECT MAX(received_at) FROM mesures WHERE node_id = m.node_id)
                GROUP BY m.node_id
            """).fetchall()
            hauteurs = dict(conn.execute("""
                SELECT m.node_id, m.water_mm
                FROM mesures m
                WHERE m.water_valid = 1 AND m.received_at = (
                    SELECT MAX(received_at) FROM mesures WHERE node_id = m.node_id AND water_valid = 1)
                GROUP BY m.node_id
            """).fetchall())
        finally:
            conn.close()
    except sqlite3.Error as e:
        print(f"[MUET] Base illisible ({e}) : aucune échéance reprise au démarrage.")
        return 0

    repris = 0
    with verrou:
        for node_id, received_at, next_min in dernieres:
            try:
                site, seuil, _ = requete_capteur(node_id, csv_path)
            except (OSError, ValueError) as e:
                print(f"[MUET] Capteur {node_id} ignoré au démarrage : {e}")
                continue
            if node_id in suivi_capteurs:   # une trame est déjà arrivée depuis le démarrage
                continue
            suivi_capteurs[node_id] = {
                "dernier_datetime": lire_date(received_at),
                "received_at": received_at,
                "next_min": next_min,
                "site": site,
                "seuil": seuil,
                "derniere_hauteur": hauteurs.get(node_id),
                "est_muet": False,
            }
            repris += 1
    print(f"[MUET] {repris} capteur(s) repris depuis la base.")
    return repris


def controler_capteurs_muets(client, instant=None, csv_path=CSV_SEUILS_PATH, json_path=PARAMETRES_PATH):
    """Un contrôle : publie une fois l'objet AL3 « muet » pour chaque capteur dont l'échéance
    est dépassée. Renvoie la liste des node_id passés muets."""
    instant = instant or maintenant()
    a_publier = []
    with verrou:
        for node_id, suivi in suivi_capteurs.items():
            if suivi["est_muet"]:
                continue   # déjà signalé : une seule publication
            try:
                site, seuil, params = params_capteur(node_id, csv_path, json_path)
            except (OSError, ValueError):
                site, seuil, params = suivi["site"], suivi["seuil"], charger_parametres(None, json_path)
            echeance = echeance_capteur(suivi, params)
            if instant <= echeance:
                continue
            suivi["est_muet"] = True
            a_publier.append((node_id, construit_json(
                node_id=node_id, site=site, seuil=seuil, hauteur=suivi["derniere_hauteur"],
                etat="muet", cause="capteur_muet", tendance=None, vitesse=None,
                temps_depassement=None, received_at=suivi["received_at"]), echeance))

    for node_id, payload_json, echeance in a_publier:
        topic = publier(client, node_id, payload_json)
        print(f"[MUET] {topic} -> capteur muet (dernière trame {suivi_capteurs[node_id]['received_at']}, "
              f"attendue au plus tard {echeance.isoformat()})")
    return [node_id for node_id, _, _ in a_publier]


def verifier_capteurs_muets(client):
    """Thread d'arrière-plan : contrôle les échéances toutes les muet_controle_s secondes."""
    while True:
        try:
            controler_capteurs_muets(client)
        except Exception as e:
            print(f"[ERREUR] Contrôle des capteurs muets impossible : {e}")
        time.sleep(max(5.0, charger_parametres()["muet_controle_s"]))


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
        mesure_valide = bool(mesure.get("water_valid", False)) and mesure.get("water_mm") is not None
        retour_json = None

        with verrou:
            # 1. Filtrage des doublons via le seq par rapport à la dernière trame en mémoire
            if node_id in derniers_etats:
                if seq_actuel is not None and derniers_etats[node_id].get("seq") == seq_actuel:
                    print(f"[INFO] Doublon détecté (seq={seq_actuel}) pour le capteur {node_id} -> Ignoré.")
                    return

            # 2. Suivi capteur muet. L'échéance part de l'heure d'arrivée ici (comme le tableau de bord) :
            #    une trame rejouée par l'injecteur avec une heure passée ne le rend pas muet.
            precedent_suivi = suivi_capteurs.get(node_id, {})
            etait_muet = precedent_suivi.get("est_muet", False)
            suivi_capteurs[node_id] = {
                "dernier_datetime": maintenant(),
                "received_at": mesure["received_at"],
                "next_min": mesure.get("next_min"),
                "site": site,
                "seuil": seuil,
                "derniere_hauteur": mesure["water_mm"] if mesure_valide else precedent_suivi.get("derniere_hauteur"),
                "est_muet": False
            }

            # 3. Récupération de l'état précédent du moteur (mémoire, sinon rejoué depuis la base)
            if node_id in derniers_etats:
                trame_prec = derniers_etats[node_id]
            else:
                trame_prec = reconstruire_etat(node_id, seuil, params, avant=mesure["received_at"])
                if trame_prec:
                    derniers_etats[node_id] = trame_prec

            # 4. Retour d'un capteur muet : un objet AL3 publié une seule fois, avec l'état connu du moteur
            if etait_muet:
                retour_json = construit_json(
                    node_id=node_id, site=site, seuil=seuil,
                    hauteur=mesure["water_mm"] if mesure_valide else None,
                    etat="alerte" if trame_prec and trame_prec["alert"] else "normal",
                    cause="retour_capteur", tendance=None, vitesse=None, temps_depassement=None,
                    received_at=mesure["received_at"])

        if retour_json:
            topic = publier(client, node_id, retour_json)
            print(f"[RETOUR] {topic} -> le capteur {node_id} émet de nouveau (seq {seq_actuel})")

        with verrou:
            # 5. Gestion des mesures invalides (0xFFFF)
            if not mesure_valide:
                print(f"[INFO] Capteur {node_id} : mesure invalide ignorée.")
                return
            trame_prec = derniers_etats.get(node_id)

            # 6. Calculs métier
            temps_dep, vitesse, tendance = calculer_temps_avant_depassement(
                mesure, trame_prec, seuil, params["saut_max_mm"])
            
            # 7. Évaluation de l'alerte (persistance, hystérésis, montée rapide : voir parametres_alerte.json)
            alerte_active, cause, nouveau_compteur = est_alerte(
                trame_prec, mesure["water_mm"], seuil, temps_dep, vitesse, params)
            etat = "alerte" if alerte_active else "normal"
            cause_json = "seuil" if cause == "hysteresis" else cause
            
            # 8. Sauvegarde en mémoire de l'état courant
            derniers_etats[node_id] = {
                "seq": seq_actuel,
                "water_mm": mesure["water_mm"],
                "received_at": mesure["received_at"],
                "alert": alerte_active,
                "nb_consecutifs_seuil": nouveau_compteur
            }
            
        # 9. Publication MQTT
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
        
        topic_sortie = publier(client, node_id, payload_json)
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
    
    print("Démarrage du moteur d'alerte...")
    # Échéances « capteur muet » reprises depuis la base (sinon un capteur déjà muet
    # avant le redémarrage ne serait jamais signalé).
    charger_echeances_depuis_base()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    # Après connect() : les objets « muet » du premier contrôle partent sur la connexion ouverte.
    thread_muet = threading.Thread(target=verifier_capteurs_muets, args=(client,), daemon=True)
    thread_muet.start()
    
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt du moteur d'alerte.")
        client.disconnect()