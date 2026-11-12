#!/usr/bin/env python3
"""
E6 — Compteurs embarqués (prototype PC).

Instrumente la boucle d'émission : à chaque trame émise, compte les trames, les
octets et le temps d'air (ToA) ; entre deux sommeils, cumule le temps d'éveil.
Exporte une ligne CSV au format figé pour les campagnes (M2/M3) :

    timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms

Point d'émission unique : toute trame passe par Compteurs.emise(). Miroir Python
de emulateur/include/compteurs.h.

Démo : rejoue un scénario (E4) avec deux modes simples et affiche les lignes CSV,
pour montrer le gain (moins de trames -> moins d'octets et de ToA).
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from rejeu import Mesure, parser_csv, rejouer

# Surcoût LoRaWAN (MHDR+FHDR+FPort+MIC) ajouté à la taille applicative pour le ToA.
OVERHEAD_LORAWAN = 13

# Colonnes d'export figées (cadrage 09/11), pour M2/M3.
COLONNES_CSV = "timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms"


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
    trames: int = 0
    octets: int = 0
    toa_ms: float = 0.0
    eveil_ms: float = 0.0
    horloge: Callable[[], float] = time.monotonic   # injectable (s) ; *1000 -> ms
    _reveil: Optional[float] = field(default=None, repr=False)

    # --- marqueurs d'éveil ---
    def reveille(self) -> None:
        self._reveil = self.horloge()

    def endort(self) -> None:
        if self._reveil is not None:
            self.eveil_ms += (self.horloge() - self._reveil) * 1000.0
            self._reveil = None

    # --- point d'émission unique ---
    def emise(self, trame: bytes) -> None:
        self.trames += 1
        self.octets += len(trame)
        self.toa_ms += temps_air_ms(len(trame) + OVERHEAD_LORAWAN, self.sf)

    # --- export ---
    def ligne_csv(self, scenario: str, mode: str,
                  timestamp: Optional[str] = None) -> str:
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (f"{ts},{scenario},{mode},{self.sf},"
                f"{self.trames},{self.octets},{self.toa_ms:.1f},{self.eveil_ms:.1f}")


def encode_stub(mesure: Mesure, node_id: int = 3, seq: int = 0) -> bytes:
    """Trame 12 octets factice (E1/encodeur de Gaetan pas encore intégré).

    Seule la LONGUEUR (12 o) compte pour les compteurs ; les champs sont indicatifs
    et suivent l'ordre du contrat (node_id, water_mm, batt, seq, status, réservés).
    """
    h = mesure.hauteur_mm & 0xFFFF
    return bytes([
        (node_id >> 8) & 0xFF, node_id & 0xFF,
        (h >> 8) & 0xFF, h & 0xFF,
        0,
        (seq >> 8) & 0xFF, seq & 0xFF,
        0,
        0, 0, 0, 0,
    ])


# --- Modes d'émission factices (en attendant E5 de Brahima) ---
# Chacun est un doit_emettre(mesure, etat) -> bool, comme l'ossature le prévoit.

def mode_naif():
    def doit_emettre(mesure: Mesure, etat) -> bool:
        return True
    return "naif", doit_emettre


def mode_frequence_fixe(intervalle_s: int = 1800):
    etat = {"dernier_t_s": None}
    def doit_emettre(mesure: Mesure, _etat) -> bool:
        d = etat["dernier_t_s"]
        if d is None or (mesure.t_s - d) >= intervalle_s:
            etat["dernier_t_s"] = mesure.t_s
            return True
        return False
    return f"freq_fixe_{intervalle_s}s", doit_emettre


def campagne(mesures, doit_emettre, sf: int) -> Compteurs:
    """Boucle firmware simulée : reveille -> doit_emettre -> encode -> emise -> endort."""
    c = Compteurs(sf=sf)
    seq = 0
    for m in rejouer(mesures, facteur=1e9):   # 1e9 = pas d'attente réelle (démo)
        c.reveille()
        if m.valide() if callable(getattr(m, "valide", None)) else m.valide:
            if doit_emettre(m, None):
                seq += 1
                c.emise(encode_stub(m, seq=seq))
        c.endort()
    return c


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="E6 — compteurs embarqués (prototype PC).")
    p.add_argument("scenario", help="fichier CSV (t_s;date_utc;hauteur_mm)")
    p.add_argument("--sf", type=int, default=7, help="spreading factor (7 à 12). Défaut 7.")
    p.add_argument("--intervalle", type=int, default=1800,
                   help="intervalle (s) du mode fréquence fixe. Défaut 1800 (30 min).")
    p.add_argument("--csv", action="store_true", help="n'afficher que le CSV")
    args = p.parse_args(argv)

    mesures = parser_csv(args.scenario)
    nom = args.scenario.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]

    modes = [mode_naif(), mode_frequence_fixe(args.intervalle)]
    print(COLONNES_CSV)
    compteurs = []
    for mode_nom, doit in modes:
        c = campagne(mesures, doit, args.sf)
        compteurs.append((mode_nom, c))
        print(c.ligne_csv(nom, mode_nom))

    if not args.csv:
        naif = compteurs[0][1]
        fixe = compteurs[1][1]
        if fixe.trames:
            gain = naif.toa_ms / fixe.toa_ms
            print(f"\n{len(mesures)} mesures, SF{args.sf}. "
                  f"Naïf : {naif.trames} trames / {naif.toa_ms:.0f} ms d'air. "
                  f"Fréquence fixe : {fixe.trames} trames / {fixe.toa_ms:.0f} ms "
                  f"(x{gain:.1f} moins de temps d'air).", file=sys.stderr)
        print("Note : eveil_ms n'est significatif que sur l'ESP32 (millis réel) ; "
              "ici il reflète le temps de calcul PC.", file=sys.stderr)


if __name__ == "__main__":
    main()
