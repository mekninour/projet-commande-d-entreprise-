// emulateur/include/modes.h
// E5 - Modes d'émission : décide, mesure par mesure, s'il faut mesurer et émettre.
//
// Modes :
//   naif  1 mesure + 1 trame toutes les 5 min (S0b du L1, référence naïve)
//   fixe  1 mesure + 1 trame toutes les 30 min (S0, rythme du contrat)
//   s4    S4 hybride fidèle au Livrable 1 (§3.4) : 3 états veille / vigilance /
//         alerte, mesure toutes les 15 min en veille, regroupement possible
//   s4v1  première version simplifiée de S4 (2 états, mesure toutes les 5 min),
//         gardée pour reproduire les chiffres présentés au client le 16/11
#pragma once
#include <stdint.h>
#include "mesure.h"

enum class Mode { NAIF, FIXE, S4, S4V1 };
enum class EtatS4 { VEILLE, VIGILANCE, ALERTE };

// Pas de mesure du format E3 : 1 mesure toutes les 5 min.
static const uint32_t PAS_MESURE_S = 300;

// Réglages des modes (valeurs par défaut modifiables au démarrage).
struct ParamsModes {
    // Mode fréquence fixe
    uint32_t periode_fixe_s      = 1800;  // référence du contrat : 1 trame / 30 min

    // Seuil d'alerte commun (s4, s4v1, témoin du banc)
    uint16_t seuil_alerte_mm     = 0;     // seuil d'alerte absolu (mm) ;
                                          // 0 = seuil relatif : base + marge
    uint16_t s4_marge_alerte_mm  = 500;   // marge du seuil relatif (mm)
    uint16_t s4_hysteresis_mm    = 50;    // retour sous seuil - hyst.
    uint32_t s4_muet_apres_s     = 1800;  // capteur muet signalé après 30 min

    // Mode S4 (L1, §3.4 et annexe B)
    uint32_t l1_mesure_veille_s   = 900;  // veille : 1 mesure / 15 min
    uint32_t l1_trame_veille_s    = 3600; // veille : 1 trame / h (4 mesures)
    uint32_t l1_mesure_crue_s     = 300;  // vigilance et alerte : 1 mesure / 5 min
    uint32_t l1_trame_crue_s      = 900;  // vigilance et alerte : 1 trame / 15 min
    uint16_t l1_marge_vigilance_mm = 250; // seuil bas = seuil d'alerte - 250 mm
                                          // (hypothèse : le L1 ne chiffre pas)
    uint16_t l1_montee_rapide_mm_h = 200; // vigilance si l'eau monte de 20 cm/h
                                          // ou plus (AL4, proposition 20/11)
    uint16_t l1_saut_max_mm       = 1500; // saut impossible entre 2 mesures :
                                          // valeur aberrante ignorée (AL4)

    // Mode S4 v1 (simplifié)
    uint32_t s4_periode_calme_s  = 3600;  // battement de cœur hors alerte
    uint32_t s4_periode_alerte_s = 900;   // cadence en alerte (15 min)
    uint16_t s4_delta_mm         = 50;    // variation qui déclenche un envoi
};

// État mémorisé entre deux mesures.
struct EtatMode {
    Mode        mode = Mode::NAIF;
    ParamsModes p;

    // Envois (mis à jour par confirmer_envoi)
    bool     deja_emis         = false;
    uint32_t t_dernier_envoi   = 0;
    uint16_t h_dernier_envoi   = 0;
    uint32_t nb_emissions      = 0;

    // Mesures prises (le capteur ne mesure pas forcément à chaque pas de 5 min)
    bool     deja_mesure       = false;
    uint32_t t_derniere_mesure = 0;
    uint32_t nb_mesures        = 0;
    uint32_t nb_aberrantes     = 0;   // mesures ignorées (saut impossible)

    // État du capteur
    bool     en_alerte         = false;
    EtatS4   etat_s4           = EtatS4::VEILLE;
    uint16_t niveau_base       = MESURE_INVALIDE;  // plus basse hauteur vue
    bool     a_eu_valide       = false;
    uint32_t t_derniere_valide = 0;
    uint16_t h_derniere_valide = 0;
    bool     muet_signale      = false;

    // Regroupement (L1) : les 3 mesures valides précédant la dernière,
    // la plus récente en premier ; MESURE_INVALIDE si absente.
    uint16_t precedentes[3]    = {MESURE_INVALIDE, MESURE_INVALIDE, MESURE_INVALIDE};
};

// Une règle de décision par mode (ne mémorise pas l'envoi).
bool decider_naif(const Mesure& m, EtatMode& e);
bool decider_fixe(const Mesure& m, EtatMode& e);
bool decider_s4  (const Mesure& m, EtatMode& e);
bool decider_s4v1(const Mesure& m, EtatMode& e);

// Décision du mode choisi au démarrage, sans mémoriser l'envoi.
bool decider_emission(const Mesure& m, EtatMode& e);

// À appeler quand la trame est réellement partie (R3 : pas si la radio a échoué).
void confirmer_envoi(const Mesure& m, EtatMode& e);

// decider_emission() puis confirmer_envoi() si oui : envoi supposé réussi.
bool doit_emettre(const Mesure& m, EtatMode& e);

// Période d'émission en vigueur, en minutes (sert pour next_min) :
// naïf 5, fixe periode_fixe_s, s4 60 en veille et 15 sinon, s4v1 calme ou alerte.
uint32_t periode_courante_min(const EtatMode& e);

// Regroupement (proposition L1 pour les octets réservés 9 à 11) : écarts, en cm
// signés, entre chacune des 3 mesures précédentes et la mesure envoyée.
// -128 (0x80) = mesure absente. Hors contrat v1.2 (octets émis à 0x00) :
// à n'utiliser qu'avec l'accord de Brest (v1.3).
void ecarts_regroupement(const EtatMode& e, uint16_t h_envoyee, int8_t ecarts[3]);

// Outils de démarrage.
void        init_etat(EtatMode& e, Mode mode, const ParamsModes& p = ParamsModes());
bool        mode_depuis_texte(const char* texte, Mode& mode);  // naif, fixe, s4, s4v1
const char* nom_mode(Mode mode);
const char* nom_etat_s4(EtatS4 etat);
