// emulateur/src/modes.cpp
#include "modes.h"
#include <string.h>

// Deux étapes séparées (alignement sur la simulation R3 de Gaetan) :
//   decider_emission() : dit s'il faut émettre ; met à jour l'état du capteur
//                        (alerte, niveau de base, capteur muet), pas l'envoi ;
//   confirmer_envoi()  : mémorise un envoi réellement parti.
// R3 n'appelle confirmer_envoi() que si la trame a pu partir ; sinon la mesure
// va dans le tampon et le mode redemandera d'émettre au pas suivant.
// doit_emettre() enchaîne les deux (comportement du banc et de test_modes).
void confirmer_envoi(const Mesure& m, EtatMode& e) {
    e.deja_emis       = true;
    e.t_dernier_envoi = m.t_s;
    if (m.valide()) e.h_dernier_envoi = m.hauteur_mm;
    e.nb_emissions++;
}

// ---------------------------------------------------------------------------
// Mode NAÏF : émet chaque mesure valide.
bool decider_naif(const Mesure& m, EtatMode&) {
    return m.valide();
}

// ---------------------------------------------------------------------------
// Mode FRÉQUENCE FIXE : une émission toutes les periode_fixe_s secondes.
// Si l'instant prévu tombe sur une mesure invalide, on émet la valide suivante.
bool decider_fixe(const Mesure& m, EtatMode& e) {
    if (!m.valide()) return false;
    return !e.deja_emis || m.t_s - e.t_dernier_envoi >= e.p.periode_fixe_s;
}

// ---------------------------------------------------------------------------
// Mode S4 HYBRIDE : périodique lent + événements.
// Seuil d'alerte : seuil_alerte_mm s'il est renseigné (seuil absolu, par
// exemple issu du fichier de seuils par site) ; sinon (0) seuil RELATIF :
// niveau de base (plus basse hauteur vue depuis le début) + s4_marge_alerte_mm,
// qui s'adapte automatiquement au zéro d'échelle de chaque station.
// Émet si : 1re mesure, retour du capteur, entrée/sortie d'alerte,
// variation >= delta depuis le dernier envoi, ou période écoulée
// (courte en alerte, longue sinon). Signale une fois un capteur muet
// en émettant une mesure invalide (0xFFFF, cf. contrat d'interface).
bool decider_s4(const Mesure& m, EtatMode& e) {
    const ParamsModes& p = e.p;

    if (!m.valide()) {
        if (e.a_eu_valide && !e.muet_signale &&
            m.t_s - e.t_derniere_valide >= p.s4_muet_apres_s) {
            e.muet_signale    = true;
            return true;                   // trame "capteur muet"
        }
        return false;
    }

    bool retour_capteur = e.muet_signale;
    e.muet_signale      = false;
    e.a_eu_valide       = true;
    e.t_derniere_valide = m.t_s;

    // Niveau de base : la plus basse hauteur vue jusqu'ici
    if (m.hauteur_mm < e.niveau_base)
        e.niveau_base = m.hauteur_mm;
    uint32_t seuil = p.seuil_alerte_mm
                   ? (uint32_t)p.seuil_alerte_mm
                   : (uint32_t)e.niveau_base + p.s4_marge_alerte_mm;

    // Alerte avec hystérésis (évite d'osciller autour du seuil)
    bool alerte_avant = e.en_alerte;
    if (!e.en_alerte && m.hauteur_mm >= seuil)
        e.en_alerte = true;
    else if (e.en_alerte &&
             (uint32_t)m.hauteur_mm + p.s4_hysteresis_mm < seuil)
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
        case Mode::S4:   return (e.en_alerte ? e.p.s4_periode_alerte_s
                                             : e.p.s4_periode_calme_s) / 60;
    }
    return 0;
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
    return false;
}

const char* nom_mode(Mode mode) {
    switch (mode) {
        case Mode::NAIF: return "naif";
        case Mode::FIXE: return "fixe";
        case Mode::S4:   return "s4";
    }
    return "?";
}
