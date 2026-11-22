#!/usr/bin/env python3
"""
Exécution d'un test R3 : coupure radio simulée, mise en tampon, puis
rattrapage étalé.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import List

from compteurs import ENTETE_RADIO, Compteurs
from rattrapage_r3 import PlanificateurRattrapage, TamponR3
from rejeu import Mesure, parser_csv, rejouer
from sim_camarades import ConfigModes, SimulateurModes, SimulateurRadio, encoder_12o


def generer_serie_test(nb_points: int = 36, pas_s: int = 300) -> List[Mesure]:
    base = datetime(2026, 11, 6, 0, 0, 0, tzinfo=timezone.utc)
    serie: List[Mesure] = []
    for i in range(nb_points):
        t_s = i * pas_s
        # Montée progressive à partir du point 15
        hauteur = 1200 + (0 if i < 15 else (i - 14) * 35)
        serie.append(
            Mesure(
                t_s=t_s,
                horodatage=base + timedelta(seconds=t_s),
                hauteur_mm=hauteur,
            )
        )
    return serie


def executer_simulation(
    mesures: List[Mesure],
    mode_nom: str = "naif",
    coupure_debut_s: int = 1500,
    coupure_fin_s: int = 4500,
    capacite_tampon: int = 30,
    max_rattrapage_par_cycle: int = 1,
    delai_rattrapage_s: int = 600,
    seuil_mm: int = 1400,
) -> None:
    modes = SimulateurModes(mode=mode_nom, cfg=ConfigModes(seuil_alerte_mm=seuil_mm))
    radio = SimulateurRadio(coupures=[(coupure_debut_s, coupure_fin_s)])
    tampon = TamponR3(capacite_max=capacite_tampon)
    planif = PlanificateurRattrapage(
        tampon=tampon,
        max_par_cycle=max_rattrapage_par_cycle,
        delai_min_s=delai_rattrapage_s,
    )
    compteurs = Compteurs(sf=7, entete=ENTETE_RADIO["lorawan"])
    seq = 0

    for m in rejouer(mesures, facteur=1e9):
        compteurs.reveille()
        radio_ok = radio.liaison_ok(m.t_s)
        alerte = m.valide and (m.hauteur_mm >= seuil_mm)
        emis_ce_cycle = 0

        # 1. Mesure courante
        if modes.doit_emettre(m):
            seq += 1
            if radio_ok:
                trame = encoder_12o(
                    m, seq, alerte, modes.periode_courante_min(), est_rattrapage=False
                )
                compteurs.emise(trame)
                modes.confirmer_envoi(m)
                emis_ce_cycle += 1
                print(
                    f"[t+{m.t_s:5d}s] LIVE        seq={seq:3d} h={m.hauteur_mm}mm "
                    f"-> OK (tampon={len(tampon)})"
                )
            else:
                tampon.empiler(m, seq_origine=seq)
                print(
                    f"[t+{m.t_s:5d}s] RADIO_KO    seq={seq:3d} h={m.hauteur_mm}mm "
                    f"-> MIS EN TAMPON (tampon={len(tampon)})"
                )

        # 2. Rattrapage étalé si la radio est revenue
        while radio_ok and planif.peut_rattraper(m.t_s, emis_ce_cycle):
            entree = tampon.valider_rattrapage()
            if entree is None:
                break
            seq += 1
            alerte_rattr = entree.mesure.valide and (entree.mesure.hauteur_mm >= seuil_mm)
            trame_rattr = encoder_12o(
                entree.mesure,
                seq,
                alerte_rattr,
                modes.periode_courante_min(),
                est_rattrapage=True,
            )
            compteurs.emise(trame_rattr)
            planif.marquer_rattrapage_emis(m.t_s)
            emis_ce_cycle += 1
            print(
                f"[t+{m.t_s:5d}s] RATTRAPAGE  seq={seq:3d} (orig_seq={entree.seq_origine}, "
                f"t_orig={entree.mesure.t_s}s, h={entree.mesure.hauteur_mm}mm) "
                f"-> OK (reste={len(tampon)})"
            )

        compteurs.endort()

    print("\n--- BILAN R3 ---")
    print(
        f"Trames émises : {compteurs.trames} | Octets : {compteurs.octets} | "
        f"ToA : {compteurs.toa_ms:.1f} ms"
    )
    print(
        f"Tampon : ajoutés={tampon.total_ajoutes}, rattrapés={tampon.total_rattrapes}, "
        f"écrasés={tampon.total_ecrases}, restants={len(tampon)}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Test simulation R3 (tampon + rattrapage).")
    p.add_argument("--scenario", default=None, help="CSV optionnel ; sinon série synthétique")
    p.add_argument("--mode", choices=["naif", "fixe", "s4"], default="naif")
    p.add_argument("--coupure-debut", type=int, default=1500)
    p.add_argument("--coupure-fin", type=int, default=4500)
    p.add_argument("--max-rattrapage", type=int, default=1)
    p.add_argument("--delai-rattrapage", type=int, default=600)
    args = p.parse_args()

    mesures = parser_csv(args.scenario) if args.scenario else generer_serie_test()
    executer_simulation(
        mesures=mesures,
        mode_nom=args.mode,
        coupure_debut_s=args.coupure_debut,
        coupure_fin_s=args.coupure_fin,
        max_rattrapage_par_cycle=args.max_rattrapage,
        delai_rattrapage_s=args.delai_rattrapage,
    )


if __name__ == "__main__":
    main()