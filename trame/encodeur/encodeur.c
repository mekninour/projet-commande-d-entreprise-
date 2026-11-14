#include "encodeur.h"

// Fonction d'encodage
void encoder_trame(uint16_t node_id, uint16_t water_mm, uint8_t batt_5mv, uint16_t seq, uint8_t status, uint8_t next_min, uint8_t *payload) {
    payload[0] = (node_id >> 8) & 0xFF;
    payload[1] = node_id & 0xFF;
    payload[2] = (water_mm >> 8) & 0xFF;
    payload[3] = water_mm & 0xFF;
    payload[4] = batt_5mv;
    payload[5] = (seq >> 8) & 0xFF;
    payload[6] = seq & 0xFF;
    payload[7] = status;
    payload[8] = next_min;
    payload[9] = 0x00;
    payload[10] = 0x00;
    payload[11] = 0x00;
}