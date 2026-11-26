#include "rattrapage_r3.h"

static uint16_t cap_effective(const EtatR3& r3) {
    if (r3.params.capacite_max == 0) return 1;
    if (r3.params.capacite_max > R3_CAPACITE_MAX) return R3_CAPACITE_MAX;
    return r3.params.capacite_max;
}

void r3_init(EtatR3& r3, const ParamsR3& p) {
    r3 = EtatR3();
    r3.params = p;
}

bool r3_vide(const EtatR3& r3) {
    return r3.taille == 0;
}

uint16_t r3_taille(const EtatR3& r3) {
    return r3.taille;
}

void r3_empiler(EtatR3& r3, const Mesure& m, uint16_t seq_origine) {
    uint16_t cap = cap_effective(r3);
    while (r3.taille >= cap) {
        r3.tete = (uint16_t)((r3.tete + 1) % R3_CAPACITE_MAX);
        r3.taille--;
        r3.total_ecrases++;
    }

    r3.buffer[r3.queue].mesure      = m;
    r3.buffer[r3.queue].seq_origine = seq_origine;
    r3.buffer[r3.queue].tentatives  = 1;

    r3.queue = (uint16_t)((r3.queue + 1) % R3_CAPACITE_MAX);
    r3.taille++;
    r3.total_ajoutes++;
}

bool r3_peut_rattraper(const EtatR3& r3, uint32_t t_s, uint8_t deja_emis_ce_cycle) {
    if (r3.taille == 0) return false;
    if (deja_emis_ce_cycle >= r3.params.max_par_cycle) return false;
    if (r3.a_rattrape && (t_s - r3.t_dernier_rattrapage_s) < r3.params.delai_min_s) {
        return false;
    }
    return true;
}

bool r3_depiler(EtatR3& r3, uint32_t t_s, EntreeR3& sortie) {
    if (r3.taille == 0) return false;

    sortie = r3.buffer[r3.tete];
    r3.tete = (uint16_t)((r3.tete + 1) % R3_CAPACITE_MAX);
    r3.taille--;
    r3.total_rattrapes++;

    r3.a_rattrape              = true;
    r3.t_dernier_rattrapage_s = t_s;
    return true;
}