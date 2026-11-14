// emulateur/include/modes.h
// E5 - Modes d'émission : décide, mesure par mesure, s'il faut émettre.
#pragma once
#include <stdint.h>
#include "mesure.h"

enum class Mode { NAIF, FIXE, S4 };

// Réglages des modes (valeurs par défaut modifiables au démarrage).
struct ParamsModes {
    // Mode fréquence fixe
    uint32_t periode_fixe_s      = 3600;  // 1 émission par heure

    // Mode S4 hybride (périodique + événementiel)
    uint32_t s4_periode_calme_s  = 3600;  // battement de cœur hors alerte
    uint32_t s4_periode_alerte_s = 900;   // cadence en alerte (15 min)
    uint16_t s4_delta_mm         = 50;    // variation qui déclenche un envoi
    uint16_t s4_marge_alerte_mm  = 500;   // alerte si hauteur >= base + marge
    uint16_t s4_hysteresis_mm    = 50;    // sortie d'alerte sous seuil - hyst.
    uint32_t s4_muet_apres_s     = 1800;  // capteur muet signalé après 30 min
};

// État mémorisé entre deux mesures.
struct EtatMode {
    Mode        mode = Mode::NAIF;
    ParamsModes p;

    bool     deja_emis         = false;
    uint32_t t_dernier_envoi   = 0;
    uint16_t h_dernier_envoi   = 0;

    // S4
    bool     en_alerte         = false;
    uint16_t niveau_base       = MESURE_INVALIDE;  // plus basse hauteur vue
    bool     a_eu_valide       = false;
    uint32_t t_derniere_valide = 0;
    bool     muet_signale      = false;

    uint32_t nb_emissions      = 0;
};

// Une version de doit_emettre par mode.
bool doit_emettre_naif(const Mesure& m, EtatMode& e);
bool doit_emettre_fixe(const Mesure& m, EtatMode& e);
bool doit_emettre_s4  (const Mesure& m, EtatMode& e);

// Point d'entrée unique : appelle la version du mode choisi au démarrage.
bool doit_emettre(const Mesure& m, EtatMode& e);

// Outils de démarrage.
void        init_etat(EtatMode& e, Mode mode, const ParamsModes& p = ParamsModes());
bool        mode_depuis_texte(const char* texte, Mode& mode);  // "naif", "fixe", "s4"
const char* nom_mode(Mode mode);