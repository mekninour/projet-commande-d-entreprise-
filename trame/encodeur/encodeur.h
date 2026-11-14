#ifndef ENCODEUR_H
#define ENCODEUR_H

#include <stdint.h>

// Déclaration de la fonction d'encodage
void encoder_trame(uint16_t node_id, uint16_t water_mm, uint8_t batt_5mv, uint16_t seq, uint8_t status, uint8_t next_min, uint8_t *payload);

#endif