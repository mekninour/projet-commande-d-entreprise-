#pragma once
#include <stdint.h>

// -----------------------------------------------------------------------------
// Ossature commune du firmware émulateur — structure Mesure.
//
// Produite par le rejeu des séries (E4) et consommée par les modes d'émission
// (E5), puis par l'encodeur de trame (E1). Ne PAS définir de format concurrent
// ailleurs : toute évolution de ce type se décide ici, avec B3.
//
// Le prototype PC (emulateur/proto/rejeu.py) est le miroir de cette struct.
// -----------------------------------------------------------------------------

// Hauteur signalant une mesure non valide (capteur muet, trou de donnée).
// Alignée sur le contrat d'interface : water_mm = 0xFFFF = invalide.
static const uint16_t MESURE_INVALIDE = 0xFFFF;

struct Mesure {
    uint32_t t_s;          // temps écoulé depuis le début du scénario, en s
    uint32_t horodatage;   // date de la mesure, en secondes epoch UTC
    uint16_t hauteur_mm;   // hauteur d'eau en mm ; MESURE_INVALIDE si non valide

    // Vrai si la mesure porte une hauteur exploitable.
    bool valide() const { return hauteur_mm != MESURE_INVALIDE; }
};
