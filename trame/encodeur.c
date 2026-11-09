#include <stdio.h>
#include <stdint.h>
#include <assert.h>

// Fonction d'encodage
void encoder_trame(uint16_t node_id, uint16_t water_mm, uint8_t batt_cv, uint16_t seq, uint8_t status, uint8_t next_min, uint8_t *payload) {
    payload[0] = (node_id >> 8) & 0xFF;
    payload[1] = node_id & 0xFF;
    payload[2] = (water_mm >> 8) & 0xFF;
    payload[3] = water_mm & 0xFF;
    payload[4] = batt_cv;
    payload[5] = (seq >> 8) & 0xFF;
    payload[6] = seq & 0xFF;
    payload[7] = status;
    payload[8] = next_min;
    payload[9] = 0x00;
    payload[10] = 0x00;
    payload[11] = 0x00;
}

int main() {
    // Données de l'exemple du contrat
    uint16_t node_id = 3;       // 0x0003
    uint16_t water_mm = 1240;   // 0x04D8
    uint8_t batt_cv = 158;      // 3,16 V -> 0x9E
    uint16_t seq = 157;         // 0x009D
    uint8_t status = 0;         // Sans alerte
    uint8_t next_min = 30;      // 30 minutes avant le prochain envoi

    uint8_t payload[12];
    encoder_trame(node_id, water_mm, batt_cv, seq, status, next_min, payload);

    // Résultat attendu du contrat : 00 03 04 D8 9E 00 9D 00 00 00 00 00
    uint8_t attendu[12] = {0x00, 0x03, 0x04, 0xD8, 0x9E, 0x00, 0x9D, 0x00, 0x1E, 0x00, 0x00, 0x00};

    for (int i = 0; i < 12; i++) {
        assert(payload[i] == attendu[i]);
    }

    printf("Succes ! La trame est parfaitement encodee selon le contrat.\n");
    return 0;
}