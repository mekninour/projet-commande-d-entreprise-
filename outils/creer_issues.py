#!/usr/bin/env python3
"""Crée les labels, le jalon "L2" et une issue par tâche du L2 (fichier taches_L2.csv).

Prérequis : GitHub CLI installé et connecté (`gh auth login`), droits d'écriture sur le dépôt.

Usage, depuis la racine du dépôt :
    python3 outils/creer_issues.py --essai     # affiche ce qui serait créé, sans rien créer
    python3 outils/creer_issues.py             # crée pour de vrai

Le script peut être relancé : une issue dont le titre existe déjà n'est pas recréée.
Les logins GitHub des membres se renseignent dans outils/membres.csv (colonne vide = pas d'assignation).
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
JALON = "L2"

LABELS = {
    # lots
    "lot:P": ("5319e7", "Pilotage et transverse"),
    "lot:A": ("1d76db", "Passerelle et serveur réseau"),
    "lot:E": ("0e8a16", "Émulateur de nœud"),
    "lot:S": ("006b75", "Traitement des données"),
    "lot:M": ("fbca04", "Mesure du gain"),
    "lot:AL": ("d93f0b", "Alertes et dashboard"),
    "lot:R": ("b60205", "Résilience"),
    "lot:G": ("c5def5", "Intégration Brest et OPAL"),
    "lot:D": ("bfd4f2", "Documentation et validation"),
    # binômes
    "B1": ("c2e0c6", "Passerelle & plateforme"),
    "B2": ("f9d0c4", "Contrat, alertes & analyse"),
    "B3": ("fef2c0", "Émulateur & campagnes"),
    "transverse": ("ededed", "Pilotage, toute l'équipe"),
    # période et état
    "socle": ("0052cc", "Avant les vacances"),
    "stretch": ("5ebeff", "Avant les vacances si le temps le permet"),
    "apres": ("d4c5f9", "Après les vacances"),
    "bloque": ("e11d21", "Tâche bloquée (voir commentaire)"),
    "option": ("cccccc", "Priorité option"),
}

BINOME = {"B1": "B1", "B2": "B2", "B3": "B3", "Transverse": "transverse"}
PERIODE = {"Socle": "socle", "Stretch": "stretch", "Après": "apres"}


def gh(args, essai, lire=False):
    if essai and not lire:
        print("  [essai] gh " + " ".join(args))
        return ""
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("  ERREUR gh " + " ".join(args[:3]) + " : " + r.stderr.strip())
        return None
    return r.stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true", help="n'écrit rien, affiche les commandes")
    a = p.parse_args()

    logins = {r["nom"]: r["github"].strip() for r in csv.DictReader(open(ICI / "membres.csv", encoding="utf-8"))}
    taches = list(csv.DictReader(open(ICI / "taches_L2.csv", encoding="utf-8")))

    # 1. Labels (--force met à jour un label existant)
    print("Labels")
    for nom, (couleur, desc) in LABELS.items():
        gh(["label", "create", nom, "--color", couleur, "--description", desc, "--force"], a.essai)

    # 2. Jalon
    print("Jalon " + JALON)
    jalons = gh(["api", "repos/{owner}/{repo}/milestones", "--jq", ".[].title"], a.essai, lire=True) or ""
    if JALON not in jalons.split("\n"):
        gh(["api", "repos/{owner}/{repo}/milestones", "-f", "title=" + JALON,
            "-f", "description=Livrable 2 : prototype, mesure du gain, dashboard, résilience"], a.essai)

    # 3. Issues
    existantes = gh(["issue", "list", "--state", "all", "--limit", "500", "--json", "title"], a.essai, lire=True)
    titres = {i["title"] for i in json.loads(existantes)} if existantes else set()

    print("Issues")
    for t in taches:
        titre = f"[{t['id']}] {t['tache']}"
        if titre in titres:
            print("  déjà là : " + titre)
            continue
        labels = ["lot:" + t["lot"], BINOME.get(t["binome"].split()[0], "transverse"), PERIODE.get(t["periode"], "apres")]
        if t["statut"] == "Bloqué":
            labels.append("bloque")
        if t["priorite"] == "Option":
            labels.append("option")
        resp = t["responsable"] + (" (co-responsable : " + t["coresp"] + ")" if t["coresp"] else "")
        corps = (
            f"**Critère de fin :** {t['critere']}\n\n"
            f"| Champ | Valeur |\n|---|---|\n"
            f"| Responsable | {resp} |\n"
            f"| Binôme | {t['binome']} |\n"
            f"| Dépend de | {t['depend']} |\n"
            f"| Matériel | {t['materiel']} |\n"
            f"| Charge estimée | {t['hp']} h·p (±30 %) |\n"
            f"| Priorité | {t['priorite']} |\n"
            f"| Période | {t['periode']} |\n\n"
            f"_Créée depuis `outils/taches_L2.csv` (statut d'origine : {t['statut']})._"
        )
        args = ["issue", "create", "--title", titre, "--body", corps, "--milestone", JALON]
        for l in labels:
            args += ["--label", l]
        for nom in (t["responsable"], t["coresp"]):
            if logins.get(nom):
                args += ["--assignee", logins[nom]]
        url = gh(args, a.essai)
        if not a.essai and url and t["statut"] == "Fait":
            gh(["issue", "close", url.strip(), "--reason", "completed"], a.essai)
        print(("  [essai] " if a.essai else "  créée : ") + titre)

    print("Terminé.")


if __name__ == "__main__":
    sys.exit(main())
