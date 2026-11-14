#!/usr/bin/env python3
"""
E3 - Préparation des scénarios Vigicrues au format figé :
    t_s;date_utc;hauteur_mm   (séparateur ;, pas de 5 min, UTF-8)

Quatre commandes :
  chercher  trouve les stations qui ont connu une crue récente
            (30 derniers jours) et crée directement les scénarios
  hubeau    télécharge les ~30 derniers jours d'une station (Hub'Eau v2)
  nettoyer  transforme un fichier brut (Hub'Eau ou export Hydroportail)
            en scénario propre au pas de 5 min
  valider   vérifie qu'un ou plusieurs scénarios respectent le format

Exemples :
  python preparer_scenarios.py chercher 2A 2B 30 34 \
         --debut 2026-11-03T00:00 --fin 2026-11-09T00:00 --creer 5
  python preparer_scenarios.py hubeau J712001001
  python preparer_scenarios.py nettoyer brut.csv scenario_01_J712001001.csv \
         --debut 2026-01-10T00:00 --fin 2026-01-14T00:00 --unite mm
  python preparer_scenarios.py valider scenario_*.csv
"""
import argparse, bisect, csv, glob, re, sys
from datetime import datetime, timedelta, timezone

PAS_S = 300                # pas de temps figé : 5 min
TROU_MAX_INTERP_S = 1800   # trou <= 30 min : interpolation linéaire
INVALIDE = 65535           # = MESURE_INVALIDE (0xFFFF) de mesure.h
UTC = timezone.utc
FORMATS = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
           "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"]


# ---------------------------------------------------------------- lecture
def lire_date(texte, heure_locale=False):
    s = re.sub(r"(Z|[+-]\d\d:?\d\d)$", "", texte.strip().strip('"'))
    for f in FORMATS:
        try:
            d = datetime.strptime(s, f)
            break
        except ValueError:
            continue
    else:
        return None
    if heure_locale:
        from zoneinfo import ZoneInfo
        return d.replace(tzinfo=ZoneInfo("Europe/Paris")).astimezone(UTC)
    return d.replace(tzinfo=UTC)


def lire_nombre(texte):
    try:
        return float(texte.strip().strip('"').replace(",", "."))
    except ValueError:
        return None


def lire_brut(chemin, unite="mm", heure_locale=False):
    """Lit un fichier brut quelconque : repère la 1re colonne date et
    la 1re colonne numérique qui la suit. Renvoie [(datetime, mm), ...]."""
    facteur = {"mm": 1, "cm": 10, "m": 1000}[unite]
    with open(chemin, encoding="utf-8-sig", errors="replace") as f:
        lignes = f.read().splitlines()
    premiere = next((l for l in lignes if l.strip()), "")
    sep = max([";", ",", "\t"], key=premiere.count)
    points = []
    for champs in csv.reader(lignes, delimiter=sep):
        for i, c in enumerate(champs):
            d = lire_date(c, heure_locale)
            if d:
                v = next((lire_nombre(x) for x in champs[i + 1:]
                          if lire_nombre(x) is not None), None)
                if v is not None:
                    points.append((d, v * facteur))
                break
    return points


# ---------------------------------------------------------------- hubeau
API = "https://hubeau.eaufrance.fr/api/v2/hydrometrie"


def _get(url, params, essais=4):
    """GET avec plusieurs essais : Hub'Eau est parfois lent à répondre."""
    import requests, time
    for n in range(1, essais + 1):
        try:
            r = requests.get(url, params=params, timeout=90)
            if r.status_code in (200, 206):
                return r.json()
            if r.status_code < 500:
                return None                       # erreur définitive
        except requests.exceptions.RequestException as e:
            print(f"    (essai {n}/{essais} échoué : {type(e).__name__})")
        time.sleep(5 * n)                          # attend 5 s, 10 s, 15 s...
    return None


def telecharger(station, debut=None, fin=None):
    """Hauteurs d'une station sur Hub'Eau (30 derniers jours max).
    Renvoie [(datetime, mm), ...] triés, ou None si la station a échoué.
    Les résultats sont gardés dans le dossier cache/ : relancer la
    commande ne retélécharge pas les stations déjà faites."""
    import json, os
    os.makedirs("cache", exist_ok=True)
    cle = f"{station}_{debut:%Y%m%d%H%M}_{fin:%Y%m%d%H%M}" if debut and fin else None
    chemin_cache = os.path.join("cache", cle + ".json") if cle else None
    if chemin_cache and os.path.exists(chemin_cache):
        with open(chemin_cache, encoding="utf-8") as f:
            return [(lire_date(d), v) for d, v in json.load(f)]

    url = API + "/observations_tr"
    params = {"code_entite": station, "grandeur_hydro": "H", "sort": "asc",
              "size": 5000, "fields": "date_obs,resultat_obs"}
    if debut:
        params["date_debut_obs"] = debut.strftime("%Y-%m-%dT%H:%M:%SZ")
    if fin:
        params["date_fin_obs"] = fin.strftime("%Y-%m-%dT%H:%M:%SZ")
    points = []
    while url:
        page = _get(url, params)
        if page is None:
            return None                            # échec : pas de cache
        for m in page.get("data", []):
            d = lire_date(m["date_obs"])
            if d and m.get("resultat_obs") is not None:
                points.append((d, float(m["resultat_obs"])))
        url, params = page.get("next"), None

    if chemin_cache:
        with open(chemin_cache, "w", encoding="utf-8") as f:
            json.dump([(d.strftime("%Y-%m-%dT%H:%M:%SZ"), v) for d, v in points], f)
    return points


def cmd_hubeau(args):
    points = telecharger(args.station) or []
    sortie = args.sortie or f"brut_{args.station}.csv"
    with open(sortie, "w", encoding="utf-8", newline="\n") as f:
        f.write("date_utc;hauteur_mm\n")
        for d, v in points:
            f.write(f"{d.strftime('%Y-%m-%dT%H:%M:%SZ')};{v}\n")
    print(f"{len(points)} mesures brutes -> {sortie}")


def cmd_chercher(args):
    """Cherche, dans des départements, les stations au pas de 5 min qui ont
    le plus monté sur une période, et crée les scénarios correspondants."""
    import requests, time
    debut, fin = lire_date(args.debut), lire_date(args.fin)
    stations = []
    for dep in args.departements:
        page = _get(API + "/referentiel/stations",
                    {"code_departement": dep, "en_service": "true", "size": 1000})
        if page is None:
            print(f"Département {dep} : serveur injoignable")
            continue
        for s in page.get("data", []):
            stations.append((s["code_station"], s.get("libelle_station", "")))
    print(f"{len(stations)} stations à examiner...")

    resultats, echecs = [], []
    for i, (code, nom) in enumerate(stations, 1):
        pts = telecharger(code, debut, fin)
        time.sleep(0.1)
        if pts is None:
            echecs.append(code)
            print(f"  [{i}/{len(stations)}] {code} ignorée (serveur injoignable)")
            continue
        if len(pts) < 100:
            continue
        ecarts = sorted((pts[j + 1][0] - pts[j][0]).total_seconds()
                        for j in range(len(pts) - 1))
        if ecarts[len(ecarts) // 2] > 360:          # pas médian > 6 min
            continue
        vals = [v for _, v in pts]
        amplitude = max(vals) - min(vals)
        resultats.append((amplitude, code, nom, pts))
        print(f"  [{i}/{len(stations)}] {code} {nom[:40]:<40} "
              f"montée {amplitude / 1000:.2f} m")

    if echecs:
        print(f"\n{len(echecs)} station(s) ignorée(s) : relance la même commande "
              "pour les réessayer (les autres sont en cache).")
    resultats.sort(key=lambda x: x[0], reverse=True)
    print("\nStations qui ont le plus monté :")
    for amp, code, nom, _ in resultats[:10]:
        print(f"  {code}  {amp / 1000:6.2f} m  {nom}")

    for n, (amp, code, nom, pts) in enumerate(resultats[:args.creer], 1):
        grille, rap = nettoyer(pts)
        sortie = f"scenario_{n:02d}_{code}.csv"
        ecrire(grille, sortie)
        print(f"\n{sortie} : {nom}, montée {amp / 1000:.2f} m, "
              f"{rap['interpolees']} interpolées, {rap['invalides']} invalides")
        valider(sortie)


# ---------------------------------------------------------------- nettoyage
def nettoyer(points, debut=None, fin=None):
    """Trie, dédoublonne, recale sur une grille de 5 min, comble les petits
    trous, marque les grands trous INVALIDE. Renvoie (grille, rapport)."""
    uniques = {}
    for d, v in points:
        uniques[d] = v                       # doublon : la dernière valeur gagne
    pts = sorted(uniques.items())
    if debut:
        pts = [p for p in pts if p[0] >= debut]
    if fin:
        pts = [p for p in pts if p[0] <= fin]
    if len(pts) < 2:
        raise SystemExit("Pas assez de mesures dans l'intervalle choisi.")

    temps = [p[0].timestamp() for p in pts]
    valeurs = [p[1] for p in pts]
    t0 = -(-int(temps[0]) // PAS_S) * PAS_S          # arrondi au 5 min supérieur
    t_fin = int(temps[-1]) // PAS_S * PAS_S
    rapport = {"interpolees": 0, "invalides": 0, "negatives": 0}
    grille = []
    t = t0
    while t <= t_fin:
        i = bisect.bisect_left(temps, t)
        if i < len(temps) and temps[i] == t:
            v = valeurs[i]
        else:
            ta, tb = temps[i - 1], temps[i]
            if tb - ta <= TROU_MAX_INTERP_S:
                va, vb = valeurs[i - 1], valeurs[i]
                v = va + (vb - va) * (t - ta) / (tb - ta)
                rapport["interpolees"] += 1
            else:
                v = None
        if v is None:
            h = INVALIDE
            rapport["invalides"] += 1
        else:
            h = round(v)
            if h < 0:                     # uint16 : pas de hauteur négative
                h = 0
                rapport["negatives"] += 1
            h = min(h, INVALIDE - 1)
        grille.append((t - t0, datetime.fromtimestamp(t, UTC), h))
        t += PAS_S
    return grille, rapport


def ecrire(grille, chemin):
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write("t_s;date_utc;hauteur_mm\n")
        for t_s, d, h in grille:
            f.write(f"{t_s};{d.strftime('%Y-%m-%dT%H:%M:%SZ')};{h}\n")


def cmd_nettoyer(args):
    debut = lire_date(args.debut) if args.debut else None
    fin = lire_date(args.fin) if args.fin else None
    points = lire_brut(args.brut, args.unite, args.heure_locale)
    print(f"{len(points)} mesures lues dans {args.brut}")
    grille, r = nettoyer(points, debut, fin)
    ecrire(grille, args.sortie)
    print(f"{len(grille)} lignes -> {args.sortie}  "
          f"(interpolées : {r['interpolees']}, invalides : {r['invalides']}, "
          f"négatives ramenées à 0 : {r['negatives']})")
    valider(args.sortie)


# ---------------------------------------------------------------- validation
def valider(chemin):
    erreurs = []
    with open(chemin, encoding="utf-8") as f:
        lignes = f.read().split("\n")
    if lignes and lignes[-1] == "":
        lignes.pop()
    if not lignes or lignes[0] != "t_s;date_utc;hauteur_mm":
        erreurs.append("en-tête incorrect")
    t_prec = None
    for n, l in enumerate(lignes[1:], start=2):
        c = l.split(";")
        if len(c) != 3:
            erreurs.append(f"ligne {n} : 3 colonnes attendues")
            continue
        if not (c[0].isdigit() and c[2].isdigit()):
            erreurs.append(f"ligne {n} : t_s et hauteur_mm doivent être des entiers")
            continue
        t, h = int(c[0]), int(c[2])
        if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", c[1]):
            erreurs.append(f"ligne {n} : date_utc mal formée")
        if t_prec is None and t != 0:
            erreurs.append("t_s doit commencer à 0")
        if t_prec is not None and t - t_prec != PAS_S:
            erreurs.append(f"ligne {n} : pas de {t - t_prec} s au lieu de {PAS_S}")
        if h > INVALIDE:
            erreurs.append(f"ligne {n} : hauteur hors plage uint16")
        t_prec = t
        if len(erreurs) > 10:
            break
    nb = len(lignes) - 1
    if erreurs:
        print(f"[ERREUR] {chemin}")
        for e in erreurs[:10]:
            print("   -", e)
        return False
    print(f"[OK] {chemin} : {nb} lignes, {nb * PAS_S / 3600:.1f} h")
    return True


def cmd_valider(args):
    fichiers = [f for motif in args.fichiers for f in glob.glob(motif)]
    ok = all([valider(f) for f in fichiers]) if fichiers else False
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    a = sp.add_parser("hubeau", help="télécharger ~30 jours depuis Hub'Eau")
    a.add_argument("station")
    a.add_argument("--sortie")
    a.set_defaults(f=cmd_hubeau)

    a = sp.add_parser("chercher", help="trouver les crues récentes et créer les scénarios")
    a.add_argument("departements", nargs="+", help="ex. 2A 2B 30 34")
    a.add_argument("--debut", required=True, help="ex. 2026-11-03T00:00 (UTC)")
    a.add_argument("--fin", required=True, help="ex. 2026-11-09T00:00 (UTC)")
    a.add_argument("--creer", type=int, default=5, help="nombre de scénarios à créer")
    a.set_defaults(f=cmd_chercher)

    a = sp.add_parser("nettoyer", help="brut -> scénario au format figé")
    a.add_argument("brut")
    a.add_argument("sortie")
    a.add_argument("--debut", help="ex. 2026-01-10T00:00 (UTC)")
    a.add_argument("--fin", help="ex. 2026-01-14T00:00 (UTC)")
    a.add_argument("--unite", choices=["mm", "cm", "m"], default="mm",
                   help="unité de la hauteur dans le fichier brut")
    a.add_argument("--heure-locale", action="store_true",
                   help="les dates du brut sont en heure française")
    a.set_defaults(f=cmd_nettoyer)

    a = sp.add_parser("valider", help="vérifier un ou plusieurs scénarios")
    a.add_argument("fichiers", nargs="+")
    a.set_defaults(f=cmd_valider)

    args = p.parse_args()
    args.f(args)