#!/usr/bin/env python3
"""
E4 — Rejeu des séries (prototype PC).

Lit un scénario CSV de hauteur d'eau et le rejoue à une horloge accélérée
réglable, en produisant des objets `Mesure` que le reste du firmware consomme
(E5 modes -> E1 encodeur -> E6 compteurs). Aucun pas de temps n'est codé en
dur : l'attente entre deux points est déduite du `t_s` réel de chaque ligne.

Miroir Python de la struct C++ `Mesure` (emulateur/include/mesure.h).
Usage : voir emulateur/proto/README.md.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterator, List

# Sentinelle "mesure invalide", alignée sur le contrat d'interface
# (water_mm = 0xFFFF signale une mesure non valide).
MESURE_INVALIDE = 0xFFFF


@dataclass
class Mesure:
    """Une mesure rejouée. Format partagé avec le module des modes (E5)."""
    t_s: int                 # temps depuis le début du scénario (s)
    horodatage: datetime     # date UTC de la mesure
    hauteur_mm: int          # hauteur d'eau en mm ; MESURE_INVALIDE si non valide

    @property
    def valide(self) -> bool:
        return self.hauteur_mm != MESURE_INVALIDE

    @property
    def epoch(self) -> int:
        """Horodatage en secondes epoch UTC (comme la struct C++)."""
        return int(self.horodatage.timestamp())

    def __str__(self) -> str:
        date = self.horodatage.strftime("%Y-%m-%dT%H:%M:%SZ")
        hauteur = "INVALIDE" if not self.valide else f"{self.hauteur_mm:>5} mm"
        return f"t+{self.t_s:>6}s  {date}  {hauteur}"


def _parse_iso(s: str) -> datetime:
    """Parse un horodatage ISO 8601 UTC (AAAA-MM-JJTHH:MM:SSZ)."""
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parser_csv(chemin: str) -> List[Mesure]:
    """Lit un CSV `t_s;date_utc;hauteur_mm` et renvoie la liste des Mesure.

    - Séparateur ';', ligne d'en-tête ignorée.
    - hauteur hors plage uint16 -> MESURE_INVALIDE.
    - Lignes mal formées -> ignorées (avertissement sur stderr).
    """
    mesures: List[Mesure] = []
    entete_vue = False
    with open(chemin, newline="", encoding="utf-8") as f:
        for n, ligne in enumerate(csv.reader(f, delimiter=";"), start=1):
            if not ligne or all(c.strip() == "" for c in ligne):
                continue
            # La 1re ligne non vide est l'en-tête si sa 1re colonne n'est pas un entier.
            if not entete_vue:
                entete_vue = True
                if not ligne[0].strip().lstrip("-").isdigit():
                    continue
            if len(ligne) < 3:
                print(f"[rejeu] ligne {n} ignorée (colonnes manquantes): {ligne}",
                      file=sys.stderr)
                continue
            try:
                t_s = int(ligne[0].strip())
                horo = _parse_iso(ligne[1].strip())
                hauteur = int(ligne[2].strip())
            except ValueError as e:
                print(f"[rejeu] ligne {n} ignorée ({e}): {ligne}", file=sys.stderr)
                continue
            if not (0 <= hauteur <= 0xFFFF) or hauteur == MESURE_INVALIDE:
                hauteur = MESURE_INVALIDE
            mesures.append(Mesure(t_s, horo, hauteur))

    if not mesures:
        raise SystemExit(f"[rejeu] aucun point exploitable dans {chemin}")
    if mesures[0].t_s != 0:
        print(f"[rejeu] attention : t_s ne commence pas à 0 (={mesures[0].t_s})",
              file=sys.stderr)
    for a, b in zip(mesures, mesures[1:]):
        if b.t_s <= a.t_s:
            print(f"[rejeu] attention : t_s non strictement croissant "
                  f"({a.t_s} -> {b.t_s})", file=sys.stderr)
    return mesures


def rejouer(mesures: List[Mesure], facteur: float = 1.0, boucle: bool = False,
            dormir: Callable[[float], None] = time.sleep) -> Iterator[Mesure]:
    """Rejoue les mesures dans l'ordre, à horloge accélérée.

    Attente réelle entre deux points = (t_s[i+1] - t_s[i]) / facteur.
    `facteur` > 0 : 1 = temps réel, 60 = 60x plus rapide.
    `boucle` : reboucle sur le scénario (1er point du cycle émis sans attente).
    `dormir` : injectable (horloge simulée pour les tests).
    """
    if facteur <= 0:
        raise ValueError("le facteur d'accélération doit être > 0")
    while True:
        precedent = None
        for m in mesures:
            if precedent is not None:
                dt_reel = (m.t_s - precedent.t_s) / facteur
                if dt_reel > 0:
                    dormir(dt_reel)
            yield m
            precedent = m
        if not boucle:
            return


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="E4 — rejeu d'un scénario CSV à horloge accélérée réglable.")
    p.add_argument("scenario", help="fichier CSV (t_s;date_utc;hauteur_mm)")
    p.add_argument("-f", "--facteur", type=float, default=60.0,
                   help="facteur d'accélération > 0 (1 = temps réel, "
                        "60 = 1 min -> 1 s). Défaut : 60.")
    p.add_argument("-b", "--boucle", action="store_true",
                   help="rejouer en boucle")
    p.add_argument("-n", "--max", type=int, default=None,
                   help="s'arrêter après N mesures")
    p.add_argument("--muet", action="store_true",
                   help="ne pas afficher chaque mesure")
    args = p.parse_args(argv)

    mesures = parser_csv(args.scenario)
    print(f"[rejeu] {len(mesures)} points chargés depuis {args.scenario} "
          f"(x{args.facteur:g}{', en boucle' if args.boucle else ''})",
          file=sys.stderr)

    debut = time.monotonic()
    n = 0
    for m in rejouer(mesures, facteur=args.facteur, boucle=args.boucle):
        n += 1
        if not args.muet:
            ecoule = time.monotonic() - debut
            print(f"[{ecoule:7.2f}s] {m}")
        # >>> point d'insertion du reste du firmware : E5(m) -> E1 -> E6 <<<
        if args.max is not None and n >= args.max:
            break
    print(f"[rejeu] terminé, {n} mesures produites.", file=sys.stderr)


if __name__ == "__main__":
    main()
