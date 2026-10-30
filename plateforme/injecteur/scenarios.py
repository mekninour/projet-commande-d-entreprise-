"""PCE 92 – S5 – Scénarios de test de l'injecteur.

Chaque scénario renvoie une liste d'« étapes ». Une étape = une trame que le
capteur émet, décrite par un dictionnaire :

    water_mm      niveau d'eau mesuré (mm)
    batt_v        tension de la batterie (V)
    alert         bit d'alerte (le nœud compare lui-même au seuil)
    sensor_fault  bit défaut capteur
    eco_mode      bit mode éco
    perdue        True = trame émise mais jamais reçue (seq avance, rien n'est publié)
    doublon       True = la même trame est publiée deux fois

Le seq est calculé par l'injecteur : il avance à chaque étape, même perdue.
"""

import random

NIVEAU_NORMAL = 1200   # mm, niveau calme de référence
BATT_NORMALE = 3.6     # V


def _etape(water_mm, seuil, batt_v=BATT_NORMALE, **options):
    """Construit une étape ; le bit d'alerte suit le seuil embarqué du nœud."""
    etape = {
        "water_mm": max(0, int(round(water_mm))),
        "batt_v": batt_v,
        "alert": water_mm >= seuil,
        "sensor_fault": False,
        "eco_mode": False,
        "perdue": False,
        "doublon": False,
    }
    etape.update(options)
    return etape


def _bruit(rng, amplitude=5):
    """Petite variation de mesure (± quelques mm)."""
    return rng.uniform(-amplitude, amplitude)


def normal(seuil, rng):
    """Rivière calme : 12 trames autour du niveau normal."""
    return [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(12)]


def montee(seuil, rng):
    """Crue lente : le niveau monte jusqu'à dépasser le seuil, puis redescend."""
    pic = seuil + 400
    montee_ = [NIVEAU_NORMAL + (pic - NIVEAU_NORMAL) * i / 15 for i in range(16)]
    descente = [pic - (pic - NIVEAU_NORMAL) * i / 8 for i in range(1, 9)]
    return [_etape(n + _bruit(rng), seuil) for n in montee_ + descente]


def montee_rapide(seuil, rng):
    """Crue éclair : +400 mm par trame, depuis un niveau bas."""
    niveaux = [NIVEAU_NORMAL] * 3 + [NIVEAU_NORMAL + 400 * i for i in range(1, 7)]
    return [_etape(n + _bruit(rng), seuil) for n in niveaux]


def pic(seuil, rng):
    """Mesure aberrante isolée : une seule trame au-dessus du seuil.
    Le moteur d'alerte (persistance) ne doit PAS déclencher d'alerte."""
    etapes = [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(10)]
    etapes[5] = _etape(seuil + 800, seuil)
    return etapes


def trame_perdue(seuil, rng):
    """Liaison radio dégradée : 3 trames perdues d'affilée (trou dans seq)."""
    etapes = [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(10)]
    for i in (4, 5, 6):
        etapes[i]["perdue"] = True
    return etapes


def doublon(seuil, rng):
    """Une trame reçue deux fois (même seq) : elle ne doit être stockée qu'une fois."""
    etapes = [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(6)]
    etapes[3]["doublon"] = True
    return etapes


def capteur_muet(seuil, rng):
    """5 trames normales puis plus rien : l'injecteur s'arrête de publier.
    C'est ce silence que le moteur d'alerte doit détecter (« hors ligne »)."""
    return [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(5)]


def batterie_faible(seuil, rng):
    """La batterie baisse ; sous 3,0 V le nœud passe en mode éco."""
    etapes = []
    for i in range(10):
        batt = round(3.4 - 0.08 * i, 2)
        etapes.append(_etape(NIVEAU_NORMAL + _bruit(rng), seuil, batt_v=batt, eco_mode=batt < 3.0))
    return etapes


def defaut_capteur(seuil, rng):
    """Le capteur renvoie des mesures incohérentes : bit défaut levé, niveau à 0."""
    etapes = [_etape(NIVEAU_NORMAL + _bruit(rng), seuil) for _ in range(8)]
    for i in (3, 4):
        etapes[i] = _etape(0, seuil, sensor_fault=True)
    return etapes


SCENARIOS = {
    "normal": normal,
    "montee": montee,
    "montee_rapide": montee_rapide,
    "pic": pic,
    "trame_perdue": trame_perdue,
    "doublon": doublon,
    "capteur_muet": capteur_muet,
    "batterie_faible": batterie_faible,
    "defaut_capteur": defaut_capteur,
}


def generer(nom, seuil, graine=92):
    """Renvoie la liste des étapes du scénario (toujours la même pour une graine donnée)."""
    return SCENARIOS[nom](seuil, random.Random(graine))
