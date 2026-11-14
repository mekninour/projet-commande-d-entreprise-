#!/usr/bin/env python3
"""
E6 — Compteurs embarqués (prototype PC).

Instrumente la boucle d'émission : à chaque trame émise, compte les trames, les
octets et le temps d'air (ToA) ; entre deux sommeils, cumule le temps d'éveil.
Exporte une ligne CSV par campagne (M2/M3) :

    timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s

Les 8 premières colonnes sont figées (cadrage du 09/11) ; `retard_alerte_s`
(décision D9 du 14/11) est ajoutée en fin de ligne.

Point d'émission unique : toute trame passe par Compteurs.emise() (décision D1).
Miroir Python de emulateur/include/compteurs.h.

Démo : rejoue un scénario (E4) avec deux modes provisoires (naïf, fréquence
fixe) en attendant les modes E5, et affiche les lignes CSV.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from rejeu import Mesure, MESURE_INVALIDE, parser_csv, rejouer

# En-tête radio ajouté à la charge utile pour le calcul du temps d'air (D9).
# LoRaWAN : MHDR (1) + FHDR (7) + FPort (1) + MIC (4) = 13 octets.
# LoRa point à point (contrat v1.2 de Brest) : aucun en-tête, 0 octet.
# Choix à confirmer à la réunion du 16/11.
ENTETE_RADIO = {"lorawan": 13, "p2p": 0}

# Colonnes d'export (M2/M3) : 8 figées le 09/11 + retard_alerte_s (D9).
COLONNES_CSV = "timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s"

# Contrat v1.2 : batterie inconnue (l'émulateur n'en a pas), bit d'alerte.
BATT_INCONNUE = 0xFF
STATUS_ALERTE = 0x01


def temps_air_ms(taille_octets: int, sf: int, bw: int = 125000, cr: int = 1,
                 n_preambule: int = 8, entete_explicite: bool = True,
                 crc: bool = True) -> float:
    """Temps d'air d'une trame LoRa, en ms (formule Semtech).

    Par défaut : BW 125 kHz, CR 4/5 (cr=1), préambule 8, en-tête explicite, CRC on.
    """
    t_sym = (2 ** sf) / bw                          # durée d'un symbole (s)
    de = 1 if (sf >= 11 and bw == 125000) else 0    # low data rate optimize
    ih = 0 if entete_explicite else 1
    crc_b = 1 if crc else 0
    num = 8 * taille_octets - 4 * sf + 28 + 16 * crc_b - 20 * ih
    den = 4 * (sf - 2 * de)
    n_payload = 8 + max(math.ceil(num / den) * (cr + 4), 0)
    t_preambule = (n_preambule + 4.25) * t_sym
    t_payload = n_payload * t_sym
    return (t_preambule + t_payload) * 1000.0


@dataclass
class Compteurs:
    sf: int = 7
    entete: int = ENTETE_RADIO["lorawan"]           # octets d'en-tête radio (D9)
    trames: int = 0
    octets: int = 0
    toa_ms: float = 0.0
    eveil_ms: float = 0.0
    retard_alerte_s: Optional[int] = None           # None = seuil jamais franchi
    horloge: Callable[[], float] = time.monotonic   # injectable (s) ; *1000 -> ms
    _reveil: Optional[float] = field(default=None, repr=False)

    # --- marqueurs d'éveil ---
    def reveille(self) -> None:
        self._reveil = self.horloge()

    def endort(self) -> None:
        if self._reveil is not None:
            self.eveil_ms += (self.horloge() - self._reveil) * 1000.0
            self._reveil = None

    # --- point d'émission unique (D1) ---
    def emise(self, trame: bytes) -> None:
        self.trames += 1
        self.octets += len(trame)
        self.toa_ms += temps_air_ms(len(trame) + self.entete, self.sf)

    # --- export ---
    def ligne_csv(self, scenario: str, mode: str,
                  timestamp: Optional[str] = None) -> str:
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        retard = "" if self.retard_alerte_s is None else str(self.retard_alerte_s)
        return (f"{ts},{scenario},{mode},{self.sf},"
                f"{self.trames},{self.octets},{self.toa_ms:.1f},{self.eveil_ms:.1f},"
                f"{retard}")


def encode_stub(mesure: Mesure, seq: int, alerte: bool, next_min: int,
                node_id: int = 3) -> bytes:
    """Trame 12 octets au format du contrat v1.2 (en attendant l'encodeur E1).

    node_id (2) | water_mm (2) | batt_5mv (1) | seq (2) | status (1) |
    next_min (1) | reserved (3). Batterie = 0xFF (inconnue) ; bit 0 de status =
    alerte (D5) ; next_min = période courante du mode, en minutes (D6).
    """
    h = mesure.hauteur_mm & 0xFFFF
    s = seq & 0xFFFF
    return bytes([
        (node_id >> 8) & 0xFF, node_id & 0xFF,
        (h >> 8) & 0xFF, h & 0xFF,
        BATT_INCONNUE,
        (s >> 8) & 0xFF, s & 0xFF,
        STATUS_ALERTE if alerte else 0x00,
        min(max(next_min, 0), 0xFF),
        0, 0, 0,
    ])


# --- Modes d'émission provisoires (en attendant E5 de Brahima) ---
# Chacun : doit_emettre(mesure) -> bool, et période courante en minutes.
# Le mode reçoit TOUTES les mesures, invalides comprises (D2) : c'est à lui
# de décider quoi en faire (ici, les ignorer, comme le naïf et le fixe d'E5).

class ModeNaif:
    nom = "naif"
    periode_min = 5                       # 1 trame par mesure (pas de 300 s)

    def doit_emettre(self, m: Mesure) -> bool:
        return m.valide


class ModeFixe:
    def __init__(self, intervalle_s: int = 1800):   # D3 : 30 min (contrat)
        self.intervalle_s = intervalle_s
        self.nom = f"fixe_{intervalle_s}s"
        self.periode_min = intervalle_s // 60
        self._dernier: Optional[int] = None

    def doit_emettre(self, m: Mesure) -> bool:
        if not m.valide:
            return False
        if self._dernier is None or (m.t_s - self._dernier) >= self.intervalle_s:
            self._dernier = m.t_s
            return True
        return False


def seuil_par_defaut(mesures: List[Mesure]) -> int:
    """Seuil relatif, comme S4 v0 : plus basse hauteur valide + 500 mm (D5)."""
    valides = [m.hauteur_mm for m in mesures if m.valide]
    return (min(valides) if valides else 0) + 500


def campagne(mesures: List[Mesure], mode, sf: int, entete: int,
             seuil_mm: int) -> Compteurs:
    """Boucle firmware simulée :
    reveille -> doit_emettre -> encode -> emettre (compteurs) -> endort.

    retard_alerte_s = délai entre le 1er franchissement du seuil (mesure valide
    >= seuil) et la 1re trame émise qui le signale (D9).
    """
    c = Compteurs(sf=sf, entete=entete)
    seq = 0
    t_franchi: Optional[int] = None
    for m in rejouer(mesures, facteur=1e9):   # 1e9 = pas d'attente réelle (banc)
        c.reveille()
        alerte = m.valide and m.hauteur_mm >= seuil_mm
        if alerte and t_franchi is None:
            t_franchi = m.t_s
        if mode.doit_emettre(m):               # toutes les mesures (D2)
            seq += 1                            # seq géré à l'émission (D6)
            c.emise(encode_stub(m, seq, alerte, mode.periode_min))
            if alerte and c.retard_alerte_s is None and t_franchi is not None:
                c.retard_alerte_s = m.t_s - t_franchi
        c.endort()
    return c


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="E6 — compteurs embarqués (prototype PC).")
    p.add_argument("scenario", help="fichier CSV (t_s;date_utc;hauteur_mm)")
    p.add_argument("--sf", type=int, default=7, help="spreading factor (7 à 12). Défaut 7.")
    p.add_argument("--radio", choices=sorted(ENTETE_RADIO), default="lorawan",
                   help="en-tête radio pour le temps d'air : lorawan (13 o) ou "
                        "p2p (0 o). Défaut lorawan.")
    p.add_argument("--intervalle", type=int, default=1800,
                   help="intervalle (s) du mode fréquence fixe. Défaut 1800 (30 min).")
    p.add_argument("--seuil", type=int, default=None,
                   help="seuil d'alerte en mm. Défaut : plus basse hauteur + 500 mm.")
    p.add_argument("--csv", action="store_true", help="n'afficher que le CSV")
    args = p.parse_args(argv)

    mesures = parser_csv(args.scenario)
    nom = args.scenario.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
    seuil = args.seuil if args.seuil is not None else seuil_par_defaut(mesures)
    entete = ENTETE_RADIO[args.radio]

    print(COLONNES_CSV)
    resultats = []
    for mode in (ModeNaif(), ModeFixe(args.intervalle)):
        c = campagne(mesures, mode, args.sf, entete, seuil)
        resultats.append((mode.nom, c))
        print(c.ligne_csv(nom, mode.nom))

    if not args.csv:
        (_, naif), (_, fixe) = resultats
        print(f"\n{len(mesures)} mesures, SF{args.sf}, radio {args.radio}, "
              f"seuil {seuil} mm.", file=sys.stderr)
        if fixe.trames:
            print(f"Naïf : {naif.trames} trames / {naif.toa_ms:.0f} ms d'air. "
                  f"Fixe : {fixe.trames} trames / {fixe.toa_ms:.0f} ms "
                  f"(x{naif.toa_ms / fixe.toa_ms:.1f} moins de temps d'air).",
                  file=sys.stderr)
        for n, c in resultats:
            r = "seuil jamais franchi" if c.retard_alerte_s is None \
                else f"{c.retard_alerte_s} s"
            print(f"Retard d'alerte {n} : {r}", file=sys.stderr)
        print("Note : eveil_ms n'est significatif que sur l'ESP32 (millis réel) ; "
              "ici il reflète le temps de calcul PC.", file=sys.stderr)


if __name__ == "__main__":
    main()
