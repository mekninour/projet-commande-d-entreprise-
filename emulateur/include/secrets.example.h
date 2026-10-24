// Modèle des identifiants LoRaWAN de l'émulateur.
// 1. Copier ce fichier en "secrets.h" dans le même dossier.
// 2. Remplir les valeurs depuis ChirpStack (fiche de l'appareil).
// secrets.h est listé dans .gitignore : il ne doit JAMAIS être commité.

#pragma once
#include <stdint.h>

#define LORAWAN_JOIN_EUI 0x0000000000000000ULL   // ex-AppEUI
#define LORAWAN_DEV_EUI  0x0000000000000000ULL   // à remplacer

// Clé racine OTAA (16 octets), à remplacer
#define LORAWAN_APP_KEY { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }

// Seulement en LoRaWAN 1.1 (sinon voir la fiche P2d, point ouvert E2)
#define LORAWAN_NWK_KEY { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }
