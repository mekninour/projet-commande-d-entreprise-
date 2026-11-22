// emulateur/src/modes.cpp
// E5 - Modes d'émission (voir modes.h). Seule implémentation de référence :
// les prototypes Python (proto/) s'alignent sur ces règles.
#include "modes.h"
#include <string.h>

// Deux étapes séparées (alignement sur la simulation R3 de Gaetan) :
//   decider_emission() : dit s'il faut émettre ; met à jour l'état du capteur
//                        (mesures prises, alerte, niveau de base, capteur muet) ;
//   confirmer_envoi()  : mémorise un envoi réellement parti.
// R3 n'appelle confirmer_envoi() que si la trame a pu partir.
// doit_emettre() enchaîne les deux (comportement du banc et de test_modes).
void confirmer_envoi(const Mesure& m, EtatMode& e) {
    e.deja_emis       = true;
    e.t_dernier_envoi = m.t_s;
    if (m.valide()) e.h_dernier_envoi = m.hauteur_mm;
    e.nb_emissions++;
}

// Seuil d'alerte : absolu s'il est renseigné, sinon niveau de base + marge.
static uint32_t seuil_alerte(const EtatMode& e) {
    return e.p.seuil_alerte_mm ? (uint32_t)e.p.seuil_alerte_mm
                               : (uint32_t)e.niveau_base + e.p.s4_marge_alerte_mm;
}

// Une mesure est prise si le pas de mesure en vigueur est écoulé.
static bool mesure_due(const Mesure& m, EtatMode& e, uint32_t pas_s) {
    if (e.deja_mesure && m.t_s - e.t_derniere_mesure < pas_s) return false;
    e.deja_mesure       = true;
    e.t_derniere_mesure = m.t_s;
    e.nb_mesures++;
    return true;
}

// ---------------------------------------------------------------------------
// Mode NAÏF (S0b) : 1 mesure + 1 trame toutes les 5 min.
bool decider_naif(const Mesure& m, EtatMode& e) {
    mesure_due(m, e, PAS_MESURE_S);
    return m.valide();
}

// ---------------------------------------------------------------------------
// Mode FRÉQUENCE FIXE (S0, contrat) : 1 mesure + 1 trame toutes les 30 min.
// Si la mesure prévue est invalide, le capteur remesure au pas suivant (5 min).
bool decider_fixe(const Mesure& m, EtatMode& e) {
    bool due = !e.deja_emis || m.t_s - e.t_dernier_envoi >= e.p.periode_fixe_s;
    if (!due) return false;
    e.nb_mesures++;
    e.deja_mesure = true;
    e.t_derniere_mesure = m.t_s;
    return m.valide();
}

// ---------------------------------------------------------------------------
// Capteur muet (commun à s4 et s4v1) : une trame 0xFFFF après s4_muet_apres_s
// sans mesure valide (contrat v1.2 : water_mm = 0xFFFF = mesure invalide).
static bool traiter_invalide(const Mesure& m, EtatMode& e) {
    if (e.a_eu_valide && !e.muet_signale &&
        m.t_s - e.t_derniere_valide >= e.p.s4_muet_apres_s) {
        e.muet_signale = true;
        return true;
    }
    return false;
}

// ---------------------------------------------------------------------------
// Mode S4, fidèle au Livrable 1 (§3.4, annexe B §1.5) :
//
//   État       Condition                                   Mesure    Trame
//   veille     situation normale                           / 15 min  1 / h (4 mesures)
//   vigilance  niveau >= seuil bas, ou montée >= 20 cm/h   / 5 min   1 / 15 min
//   alerte     niveau >= seuil d'alerte                    / 5 min   immédiate, puis
//                                                                    1 / 15 min, bit 0
//
// Sorties d'état avec hystérésis (s4_hysteresis_mm). Fin d'alerte envoyée tout
// de suite. Valeur aberrante (saut > l1_saut_max_mm) ignorée, comme la médiane
// de 5 tirs le ferait sur le vrai capteur. Mode éco et défaut capteur : non
// codés (bits 1 à 7 de status interdits par le contrat v1.2).
bool decider_s4(const Mesure& m, EtatMode& e) {
    const ParamsModes& p = e.p;
    uint32_t pas = (e.etat_s4 == EtatS4::VEILLE) ? p.l1_mesure_veille_s : p.l1_mesure_crue_s;
    if (!mesure_due(m, e, pas)) return false;

    if (!m.valide()) return traiter_invalide(m, e);

    // Garde-fou : saut physiquement impossible entre deux mesures.
    if (e.a_eu_valide) {
        int32_t saut = (int32_t)m.hauteur_mm - (int32_t)e.h_derniere_valide;
        if (saut < 0) saut = -saut;
        if (saut > (int32_t)p.l1_saut_max_mm) { e.nb_aberrantes++; return false; }
    }

    bool retour_capteur = e.muet_signale;
    e.muet_signale = false;

    // Vitesse de montée entre les deux dernières mesures valides (2 mesures).
    bool montee_rapide = false;
    if (e.a_eu_valide && m.t_s > e.t_derniere_valide) {
        int32_t dh = (int32_t)m.hauteur_mm - (int32_t)e.h_derniere_valide;
        uint32_t dt = m.t_s - e.t_derniere_valide;
        if (dh > 0 && (uint64_t)dh * 3600u >= (uint64_t)p.l1_montee_rapide_mm_h * dt)
            montee_rapide = true;
    }

    // Historique pour le regroupement, puis mesure courante.
    if (e.a_eu_valide) {
        e.precedentes[2] = e.precedentes[1];
        e.precedentes[1] = e.precedentes[0];
        e.precedentes[0] = e.h_derniere_valide;
    }
    e.a_eu_valide       = true;
    e.t_derniere_valide = m.t_s;
    e.h_derniere_valide = m.hauteur_mm;
    if (m.hauteur_mm < e.niveau_base) e.niveau_base = m.hauteur_mm;

    uint32_t seuil = seuil_alerte(e);
    uint32_t seuil_bas = seuil > p.l1_marge_vigilance_mm ? seuil - p.l1_marge_vigilance_mm : 0;
    uint32_t h = m.hauteur_mm, hyst = p.s4_hysteresis_mm;

    EtatS4 avant = e.etat_s4;
    EtatS4 apres;
    if (h >= seuil)                                          apres = EtatS4::ALERTE;
    else if (avant == EtatS4::ALERTE && h + hyst >= seuil)   apres = EtatS4::ALERTE;
    else if (h >= seuil_bas || montee_rapide)                apres = EtatS4::VIGILANCE;
    else if (avant != EtatS4::VEILLE && h + hyst >= seuil_bas) apres = EtatS4::VIGILANCE;
    else                                                     apres = EtatS4::VEILLE;
    e.etat_s4   = apres;
    e.en_alerte = (apres == EtatS4::ALERTE);

    bool entree_alerte = (apres == EtatS4::ALERTE) && (avant != EtatS4::ALERTE);
    bool sortie_alerte = (avant == EtatS4::ALERTE) && (apres != EtatS4::ALERTE);
    uint32_t periode = (apres == EtatS4::VEILLE) ? p.l1_trame_veille_s : p.l1_trame_crue_s;

    return !e.deja_emis
        || retour_capteur
        || entree_alerte
        || sortie_alerte
        || m.t_s - e.t_dernier_envoi >= periode;
}

// ---------------------------------------------------------------------------
// Mode S4 v1 (première version, simplifiée) : périodique lent + événements.
// Mesure toutes les 5 min. Émet si : 1re mesure, retour du capteur,
// entrée/sortie d'alerte, variation >= delta depuis le dernier envoi, ou
// période écoulée (courte en alerte, longue sinon).
bool decider_s4v1(const Mesure& m, EtatMode& e) {
    const ParamsModes& p = e.p;
    mesure_due(m, e, PAS_MESURE_S);

    if (!m.valide()) return traiter_invalide(m, e);

    bool retour_capteur = e.muet_signale;
    e.muet_signale      = false;
    e.a_eu_valide       = true;
    e.t_derniere_valide = m.t_s;
    e.h_derniere_valide = m.hauteur_mm;

    if (m.hauteur_mm < e.niveau_base) e.niveau_base = m.hauteur_mm;
    uint32_t seuil = seuil_alerte(e);

    bool alerte_avant = e.en_alerte;
    if (!e.en_alerte && m.hauteur_mm >= seuil)
        e.en_alerte = true;
    else if (e.en_alerte && (uint32_t)m.hauteur_mm + p.s4_hysteresis_mm < seuil)
        e.en_alerte = false;

    int32_t variation = (int32_t)m.hauteur_mm - (int32_t)e.h_dernier_envoi;
    if (variation < 0) variation = -variation;
    uint32_t periode = e.en_alerte ? p.s4_periode_alerte_s : p.s4_periode_calme_s;

    return !e.deja_emis
        || retour_capteur
        || e.en_alerte != alerte_avant
        || variation >= (int32_t)p.s4_delta_mm
        || m.t_s - e.t_dernier_envoi >= periode;
}

// ---------------------------------------------------------------------------
bool decider_emission(const Mesure& m, EtatMode& e) {
    switch (e.mode) {
        case Mode::NAIF: return decider_naif(m, e);
        case Mode::FIXE: return decider_fixe(m, e);
        case Mode::S4:   return decider_s4(m, e);
        case Mode::S4V1: return decider_s4v1(m, e);
    }
    return false;
}

bool doit_emettre(const Mesure& m, EtatMode& e) {
    if (!decider_emission(m, e)) return false;
    confirmer_envoi(m, e);
    return true;
}

uint32_t periode_courante_min(const EtatMode& e) {
    switch (e.mode) {
        case Mode::NAIF: return PAS_MESURE_S / 60;
        case Mode::FIXE: return e.p.periode_fixe_s / 60;
        case Mode::S4:   return (e.etat_s4 == EtatS4::VEILLE ? e.p.l1_trame_veille_s
                                                             : e.p.l1_trame_crue_s) / 60;
        case Mode::S4V1: return (e.en_alerte ? e.p.s4_periode_alerte_s
                                             : e.p.s4_periode_calme_s) / 60;
    }
    return 0;
}

void ecarts_regroupement(const EtatMode& e, uint16_t h_envoyee, int8_t ecarts[3]) {
    for (int k = 0; k < 3; ++k) {
        uint16_t hp = e.precedentes[k];
        if (hp == MESURE_INVALIDE || h_envoyee == MESURE_INVALIDE) { ecarts[k] = -128; continue; }
        int32_t cm = ((int32_t)hp - (int32_t)h_envoyee);
        cm = (cm >= 0) ? (cm + 5) / 10 : -((-cm + 5) / 10);   // arrondi au cm
        if (cm > 127) cm = 127;
        if (cm < -127) cm = -127;
        ecarts[k] = (int8_t)cm;
    }
}

void init_etat(EtatMode& e, Mode mode, const ParamsModes& p) {
    e = EtatMode();
    e.mode = mode;
    e.p = p;
}

bool mode_depuis_texte(const char* t, Mode& mode) {
    if (!t) return false;
    if (strcmp(t, "naif") == 0) { mode = Mode::NAIF; return true; }
    if (strcmp(t, "fixe") == 0) { mode = Mode::FIXE; return true; }
    if (strcmp(t, "s4")   == 0) { mode = Mode::S4;   return true; }
    if (strcmp(t, "s4v1") == 0) { mode = Mode::S4V1; return true; }
    return false;
}

const char* nom_mode(Mode mode) {
    switch (mode) {
        case Mode::NAIF: return "naif";
        case Mode::FIXE: return "fixe";
        case Mode::S4:   return "s4";
        case Mode::S4V1: return "s4v1";
    }
    return "?";
}

const char* nom_etat_s4(EtatS4 etat) {
    switch (etat) {
        case EtatS4::VEILLE:    return "veille";
        case EtatS4::VIGILANCE: return "vigilance";
        case EtatS4::ALERTE:    return "alerte";
    }
    return "?";
}
