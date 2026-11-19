// emulateur/tests/test_modes.cpp
// Banc d'essai autonome de E5 : lit un scénario CSV (format E3) et affiche
// les décisions d'émission. Ne remplace PAS le rejeu E4, sert juste à tester.
//
// Compilation : g++ -std=c++11 -Iinclude src/modes.cpp tests/test_modes.cpp -o test_modes
// Usage       : ./test_modes <naif|fixe|s4> scenario.csv [-v] [--seuil MM]
//   -v          détaille chaque émission (heure, hauteur, période en vigueur)
//   --seuil MM  seuil d'alerte absolu de S4 (par défaut 0 = seuil relatif)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "modes.h"

int main(int argc, char** argv) {
    Mode mode;
    if (argc < 3 || !mode_depuis_texte(argv[1], mode)) {
        fprintf(stderr, "Usage : %s <naif|fixe|s4> scenario.csv [-v] [--seuil MM]\n", argv[0]);
        return 1;
    }
    bool verbeux = false;
    ParamsModes params;
    for (int i = 3; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0) verbeux = true;
        else if (strcmp(argv[i], "--seuil") == 0 && i + 1 < argc)
            params.seuil_alerte_mm = (uint16_t)atoi(argv[++i]);
    }

    FILE* f = fopen(argv[2], "r");
    if (!f) { perror(argv[2]); return 1; }

    EtatMode etat;
    init_etat(etat, mode, params);      // mode choisi au démarrage

    char ligne[128];
    if (!fgets(ligne, sizeof ligne, f)) { fclose(f); return 1; }  // en-tête
    unsigned nb = 0, nb_invalides = 0;
    while (fgets(ligne, sizeof ligne, f)) {
        char date[32];
        unsigned long t, h;
        if (sscanf(ligne, "%lu;%31[^;];%lu", &t, date, &h) != 3) continue;
        Mesure m;
        m.t_s        = (uint32_t)t;
        m.horodatage = 0;               // fourni par le rejeu E4 dans l'émulateur
        m.hauteur_mm = (uint16_t)h;
        nb++;
        if (!m.valide()) nb_invalides++;

        if (doit_emettre(m, etat) && verbeux) {
            if (m.valide()) printf("EMET  t=%6lus  %s  %5lu mm  (periode %u min)\n",
                                   t, date, h, (unsigned)periode_courante_min(etat));
            else            printf("EMET  t=%6lus  %s  CAPTEUR MUET\n", t, date);
        }
    }
    fclose(f);

    printf("Mode %-4s : %u mesures (%u invalides) -> %u emissions (%.1f %%)\n",
           nom_mode(mode), nb, nb_invalides, (unsigned)etat.nb_emissions,
           nb ? 100.0 * etat.nb_emissions / nb : 0.0);
    return 0;
}
