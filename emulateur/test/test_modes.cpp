// emulateur/tests/test_modes.cpp
// Banc d'essai autonome de E5 : lit un scénario CSV (format E3) et affiche
// les décisions d'émission. Ne remplace PAS le rejeu E4, sert juste à tester.
//
// Compilation : g++ -std=c++11 -Iinclude src/modes.cpp tests/test_modes.cpp -o test_modes
// Usage       : ./test_modes <naif|fixe|s4> scenario.csv [-v]
#include <stdio.h>
#include <string.h>
#include "modes.h"

int main(int argc, char** argv) {
    Mode mode;
    if (argc < 3 || !mode_depuis_texte(argv[1], mode)) {
        fprintf(stderr, "Usage : %s <naif|fixe|s4> scenario.csv [-v]\n", argv[0]);
        return 1;
    }
    bool verbeux = (argc > 3 && strcmp(argv[3], "-v") == 0);

    FILE* f = fopen(argv[2], "r");
    if (!f) { perror(argv[2]); return 1; }

    EtatMode etat;
    init_etat(etat, mode);              // mode choisi au démarrage

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
            if (m.valide()) printf("EMET  t=%6lus  %s  %5lu mm\n", t, date, h);
            else            printf("EMET  t=%6lus  %s  CAPTEUR MUET\n", t, date);
        }
    }
    fclose(f);

    printf("Mode %-4s : %u mesures (%u invalides) -> %u emissions (%.1f %%)\n",
           nom_mode(mode), nb, nb_invalides, (unsigned)etat.nb_emissions,
           nb ? 100.0 * etat.nb_emissions / nb : 0.0);
    return 0;
}
