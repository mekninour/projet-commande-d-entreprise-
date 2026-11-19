#include <stdio.h>
#include "encodeur.h"

#define MAX_LIGNE 256

int main() {
    FILE *fichier = fopen("../exemples/exemples_trames.csv", "r");
    if (fichier == NULL) {
        perror("Erreur d'ouverture du fichier CSV");
        return 1;
    }

    char ligne[MAX_LIGNE];
    int num_ligne = 0;
    int tests_ussies = 0;

    while (fgets(ligne, sizeof(ligne), fichier) != NULL) {
        num_ligne++;
        if (num_ligne == 1) continue; // Ignorer l'en-tête

        char nom[64];
        char hex_str[64];
        uint16_t node_id;
        uint16_t water_mm;
        uint8_t batt_raw;
        uint16_t seq;
        uint8_t status;
        uint8_t next_min;
        char source[128];

        // Lecture de la ligne du CSV (séparateur virgule)
        int ret = sscanf(ligne, "%63[^,],%63[^,],%hu,%hu,%hhu,%hu,%hhu,%hhu,%127[^\n]", 
                         nom, hex_str, &node_id, &water_mm, &batt_raw, &seq, &status, &next_min, source);

        if (ret >= 8) {
            // 1. Génération du payload via votre fonction C
            uint8_t payload_genere[12];
            encoder_trame(node_id, water_mm, batt_raw, seq, status, next_min, payload_genere);

            // 2. Conversion de la chaîne hex_str ("00 03 01 ...") en tableau d'octets attendus
            uint8_t payload_attendu[12];
            unsigned int valeurs[12];
            sscanf(hex_str, "%x %x %x %x %x %x %x %x %x %x %x %x", 
                   &valeurs[0], &valeurs[1], &valeurs[2], &valeurs[3], 
                   &valeurs[4], &valeurs[5], &valeurs[6], &valeurs[7], 
                   &valeurs[8], &valeurs[9], &valeurs[10], &valeurs[11]);
            
            for(int i = 0; i < 12; i++) {
                payload_attendu[i] = (uint8_t)valeurs[i];
            }

            // 3. Comparaison (Vérification automatique)
            int echec = 0;
            for(int i = 0; i < 12; i++) {
                if (payload_genere[i] != payload_attendu[i]) {
                    echec = 1;
                    break;
                }
            }

            if (echec) {
                printf("[ECHEC] Ligne %d (%s) : Le payload ne correspond pas au CSV !\n", num_ligne, nom);
            } else {
                printf("[SUCCES] Ligne %d (%s) valide.\n", num_ligne, nom);
                tests_ussies++;
            }
        }
    }
    return 0;
}