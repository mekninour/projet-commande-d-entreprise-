#!/usr/bin/env python3
"""
Simulation des modules camarades (E5 modes, E1 encodeur 12o, E6 compteurs & radio)
pour tester R3 en isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from compteurs import BATT_INCONNUE, STATUS_ALERTE, Compteurs
from rejeu import Mesure

STATUS_RATTRAPAGE = 0x02


@dataclass
class ConfigModes:
    periode_fixe_s: int = 1800
    seuil_alerte_mm: int = 0          # 0 => seuil relatif (min + marge)
    s4_marge_alerte_mm: int = 500
    s4_hysteresis_mm: int = 50
    s4_delta_mm: int = 100
    s4_periode_calme_s: int = 3600
    s4_periode_alerte_s: int = 600
    s4_muet_apres_s: int = 1800


@dataclass
class EtatModeSim:
    mode: str
    cfg: ConfigModes
    deja_emis: bool = False
    t_dernier_envoi: int = 0
    h_dernier_envoi: int = 0
    a_eu_valide: bool = False
    t_derniere_valide: int = 0
    niveau_base: int = 0xFFFF
    en_alerte: bool = False
    muet_signale: bool = False


class SimulateurModes:
    def __init__(self, mode: str, cfg: Optional[ConfigModes] = None) -> None:
        if mode not in ("naif", "fixe", "s4"):
            raise ValueError(f"Mode inconnu : {mode}")
        self.etat = EtatModeSim(mode=mode, cfg=cfg or ConfigModes())

    def periode_courante_min(self) -> int:
        c = self.etat.cfg
        if self.etat.mode == "naif":
            return 5
        if self.etat.mode == "fixe":
            return max(1, c.periode_fixe_s // 60)
        p_s = c.s4_periode_alerte_s if self.etat.en_alerte else c.s4_periode_calme_s
        return max(1, p_s // 60)

    def doit_emettre(self, m: Mesure) -> bool:
        e = self.etat
        c = e.cfg

        if e.mode == "naif":
            return m.valide

        if e.mode == "fixe":
            if not m.valide:
                return False
            return (not e.deja_emis) or ((m.t_s - e.t_dernier_envoi) >= c.periode_fixe_s)

        # Mode S4 hybride
        if not m.valide:
            if (
                e.a_eu_valide
                and not e.muet_signale
                and (m.t_s - e.t_derniere_valide) >= c.s4_muet_apres_s
            ):
                e.muet_signale = True
                return True
            return False

        retour_capteur = e.muet_signale
        e.muet_signale = False
        e.a_eu_valide = True
        e.t_derniere_valide = m.t_s

        if m.hauteur_mm < e.niveau_base:
            e.niveau_base = m.hauteur_mm

        seuil = (
            c.seuil_alerte_mm
            if c.seuil_alerte_mm > 0
            else e.niveau_base + c.s4_marge_alerte_mm
        )

        alerte_avant = e.en_alerte
        if not e.en_alerte and m.hauteur_mm >= seuil:
            e.en_alerte = True
        elif e.en_alerte and (m.hauteur_mm + c.s4_hysteresis_mm) < seuil:
            e.en_alerte = False

        variation = abs(m.hauteur_mm - e.h_dernier_envoi)
        periode = c.s4_periode_alerte_s if e.en_alerte else c.s4_periode_calme_s

        return (
            not e.deja_emis
            or retour_capteur
            or (e.en_alerte != alerte_avant)
            or (variation >= c.s4_delta_mm)
            or ((m.t_s - e.t_dernier_envoi) >= periode)
        )

    def confirmer_envoi(self, m: Mesure) -> None:
        self.etat.deja_emis = True
        self.etat.t_dernier_envoi = m.t_s
        if m.valide:
            self.etat.h_dernier_envoi = m.hauteur_mm


def encoder_12o(
    mesure: Mesure,
    seq: int,
    alerte: bool,
    next_min: int,
    est_rattrapage: bool = False,
    node_id: int = 3,
) -> bytes:
    """Encode une trame de 12 octets (compatible contrat v1.2 + flag rattrapage)."""
    h = mesure.hauteur_mm & 0xFFFF
    s = seq & 0xFFFF
    status = (STATUS_ALERTE if alerte else 0x00) | (
        STATUS_RATTRAPAGE if est_rattrapage else 0x00
    )
    return bytes([
        (node_id >> 8) & 0xFF,
        node_id & 0xFF,
        (h >> 8) & 0xFF,
        h & 0xFF,
        BATT_INCONNUE,
        (s >> 8) & 0xFF,
        s & 0xFF,
        status,
        min(max(next_min, 0), 0xFF),
        0,
        0,
        0,
    ])


@dataclass
class SimulateurRadio:
    """Simule des fenêtres de perte radio [debut_s, fin_s[ sur l'axe t_s."""

    coupures: List[Tuple[int, int]] = field(default_factory=list)

    def liaison_ok(self, t_s: int) -> bool:
        for debut, fin in self.coupures:
            if debut <= t_s < fin:
                return False
        return True