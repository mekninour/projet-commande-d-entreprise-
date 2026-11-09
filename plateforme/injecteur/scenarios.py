"""PCE 92 – S5 – Scénarios de test de l'injecteur (contrat v1.2, V1).

Chaque scénario renvoie une liste d'« étapes ». Une étape = une trame que le
capteur émet, décrite par un dictionnaire :

    water_mm   niveau d'eau au-dessus du sol, en mm (None = mesure invalide, 0xFFFF)
    batt_v     tension de la batterie, en V (None = inconnue, 0xFF)
    perdue     True = trame émise mais jamais reçue (seq avance, rien n'est publié)
    doublon    True = la même trame est reçue deux fois

Le bit d'alerte est calculé par l'injecteur, comme le ferait le nœud :
niveau >= seuil (300 mm par défaut, repère Géorisques).
Le seq est calculé par l'injecteur : il avance à chaque étape, même perdue.
"""

import random

NIVEAU_NORMAL = 30   # mm au-dessus du sol : rivière dans son lit
BATT_NORMALE = 3.30  # V, batterie LiFePO4 en fonctionnement normal


def _etape(water_mm, batt_v=BATT_NORMALE, **options):
    etape = {"water_mm": water_mm, "batt_v": batt_v, "perdue": False, "doublon": False}
    etape.update(options)
    return etape


def _niveau(valeur, rng, amplitude=3):
    """Mesure avec une petite variation (± quelques mm), jamais négative."""
    return max(0, int(round(valeur + rng.uniform(-amplitude, amplitude))))


def normal(seuil, rng):
    """Rivière calme : 12 trames autour de 30 mm, sans alerte."""
    return [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(12)]


def montee(seuil, rng):
    """Crue lente : le niveau monte au-delà du seuil puis redescend."""
    pic = seuil + 150
    montee_ = [NIVEAU_NORMAL + (pic - NIVEAU_NORMAL) * i / 12 for i in range(13)]
    descente = [pic - (pic - NIVEAU_NORMAL) * i / 8 for i in range(1, 9)]
    return [_etape(_niveau(n, rng)) for n in montee_ + descente]


def montee_rapide(seuil, rng):
    """Crue éclair : +120 mm par trame, depuis un niveau bas."""
    niveaux = [NIVEAU_NORMAL] * 3 + [NIVEAU_NORMAL + 120 * i for i in range(1, 6)]
    return [_etape(_niveau(n, rng)) for n in niveaux]


def pic(seuil, rng):
    """Mesure aberrante isolée : une seule trame au-dessus du seuil."""
    etapes = [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(10)]
    etapes[5] = _etape(seuil + 200)
    return etapes


def trame_perdue(seuil, rng):
    """Liaison radio dégradée : 3 trames perdues d'affilée (trou dans seq)."""
    etapes = [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(10)]
    for i in (4, 5, 6):
        etapes[i]["perdue"] = True
    return etapes


def doublon(seuil, rng):
    """Une trame reçue deux fois (même seq) : écart de seq nul = doublon."""
    etapes = [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(6)]
    etapes[3]["doublon"] = True
    return etapes


def capteur_muet(seuil, rng):
    """5 trames normales puis plus rien : le capteur ne respecte plus son next_min."""
    return [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(5)]


def mesure_invalide(seuil, rng):
    """Le capteur renvoie deux mesures invalides (water_mm = 0xFFFF)."""
    etapes = [_etape(_niveau(NIVEAU_NORMAL, rng)) for _ in range(8)]
    for i in (3, 4):
        etapes[i]["water_mm"] = None
    return etapes


def batterie_faible(seuil, rng):
    """La batterie baisse de 3,30 V à 2,85 V ; la dernière trame ne connaît plus la tension."""
    etapes = [_etape(_niveau(NIVEAU_NORMAL, rng), batt_v=round(3.30 - 0.05 * i, 2)) for i in range(10)]
    etapes.append(_etape(_niveau(NIVEAU_NORMAL, rng), batt_v=None))
    return etapes


SCENARIOS = {
    "normal": normal,
    "montee": montee,
    "montee_rapide": montee_rapide,
    "pic": pic,
    "trame_perdue": trame_perdue,
    "doublon": doublon,
    "capteur_muet": capteur_muet,
    "mesure_invalide": mesure_invalide,
    "batterie_faible": batterie_faible,
}


def generer(nom, seuil, graine=92):
    """Renvoie la liste des étapes du scénario (toujours la même pour une graine donnée)."""
    return SCENARIOS[nom](seuil, random.Random(graine))
