#pragma once
#include <stdint.h>
#include "mesure.h"

static const uint16_t R3_CAPACITE_MAX = 64;

struct EntreeR3 {
    Mesure   mesure;
    uint16_t seq_origine = 0;
    uint8_t  tentatives  = 0;
};

struct ParamsR3 {
    uint16_t capacite_max  = R3_CAPACITE_MAX; // <= R3_CAPACITE_MAX
    uint8_t  max_par_cycle = 1;               // max trames de rattrapage par pas
    uint32_t delai_min_s   = 600;             // espacement minimal (s) entre rattrapages
};

struct EtatR3 {
    ParamsR3 params;
    EntreeR3 buffer[R3_CAPACITE_MAX];
    uint16_t tete          = 0;
    uint16_t queue         = 0;
    uint16_t taille        = 0;

    uint32_t total_ajoutes   = 0;
    uint32_t total_ecrases   = 0;
    uint32_t total_rattrapes = 0;

    bool     a_rattrape              = false;
    uint32_t t_dernier_rattrapage_s = 0;
};

void     r3_init(EtatR3& r3, const ParamsR3& p = ParamsR3());
bool     r3_vide(const EtatR3& r3);
uint16_t r3_taille(const EtatR3& r3);
void     r3_empiler(EtatR3& r3, const Mesure& m, uint16_t seq_origine);
bool     r3_peut_rattraper(const EtatR3& r3, uint32_t t_s, uint8_t deja_emis_ce_cycle);
bool     r3_depiler(EtatR3& r3, uint32_t t_s, EntreeR3& sortie);