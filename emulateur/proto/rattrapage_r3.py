#!/usr/bin/env python3
"""
R3 — Mémoire tampon côté nœud et rattrapage étalé (prototype PC).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from rejeu import Mesure


@dataclass
class EntreeTampon:
    mesure: Mesure
    seq_origine: int
    tentatives: int = 1


class TamponR3:
    """Mémoire tampon FIFO bornée pour conserver les trames non transmises."""

    def __init__(self, capacite_max: int = 50) -> None:
        if capacite_max <= 0:
            raise ValueError("capacite_max doit être > 0")
        self.capacite_max = capacite_max
        self._file: Deque[EntreeTampon] = deque()
        self.total_ajoutes: int = 0
        self.total_ecrases: int = 0
        self.total_rattrapes: int = 0

    def __len__(self) -> int:
        return len(self._file)

    @property
    def vide(self) -> bool:
        return len(self._file) == 0

    def empiler(self, mesure: Mesure, seq_origine: int) -> None:
        if len(self._file) >= self.capacite_max:
            self._file.popleft()  # écrase la plus ancienne si saturation
            self.total_ecrases += 1
        self._file.append(EntreeTampon(mesure=mesure, seq_origine=seq_origine))
        self.total_ajoutes += 1

    def prochaine_rattrapage(self) -> Optional[EntreeTampon]:
        if not self._file:
            return None
        return self._file[0]

    def valider_rattrapage(self) -> Optional[EntreeTampon]:
        if not self._file:
            return None
        entree = self._file.popleft()
        self.total_rattrapes += 1
        return entree


class PlanificateurRattrapage:
    """Étale la réémission des données conservées lors du retour de la radio.

    Paramètres choisis par défaut (ajustables pour R3 / R4) :
    - max_par_cycle : nb max de trames de rattrapage envoyées sur un même pas
      (1 par défaut pour éviter les rafales).
    - delai_min_s : espacement minimal (en secondes de scénario `t_s`) entre
      deux trames de rattrapage.
    """

    def __init__(
        self,
        tampon: TamponR3,
        max_par_cycle: int = 1,
        delai_min_s: int = 300,
    ) -> None:
        self.tampon = tampon
        self.max_par_cycle = max(1, max_par_cycle)
        self.delai_min_s = max(0, delai_min_s)
        self._dernier_rattrapage_t_s: Optional[int] = None

    def peut_rattraper(self, t_s_courant: int, deja_emis_ce_cycle: int) -> bool:
        if self.tampon.vide:
            return False
        if deja_emis_ce_cycle >= self.max_par_cycle:
            return False
        if (
            self._dernier_rattrapage_t_s is not None
            and (t_s_courant - self._dernier_rattrapage_t_s) < self.delai_min_s
        ):
            return False
        return True

    def marquer_rattrapage_emis(self, t_s_courant: int) -> None:
        self._dernier_rattrapage_t_s = t_s_courant