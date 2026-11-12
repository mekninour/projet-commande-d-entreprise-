#pragma once
#include <stdint.h>
#include <math.h>

// -----------------------------------------------------------------------------
// E6 — Compteurs embarqués.
//
// Point d'émission unique : toute trame émise passe par Compteurs::emise().
// C'est là, et nulle part ailleurs, que montent les compteurs d'émission
// (trames, octets, temps d'air). L'éveil est encadré par reveille()/endort().
//
// Export série figé (campagnes M2/M3) :
//   timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms
// -----------------------------------------------------------------------------

// Surcoût LoRaWAN (MHDR+FHDR+FPort+MIC) ajouté à la taille applicative pour le
// temps d'air. Les « octets » comptés restent la charge utile applicative.
static const uint8_t OVERHEAD_LORAWAN = 13;

// Temps d'air d'une trame LoRa, en ms (formule Semtech).
// Hypothèses : BW 125 kHz, CR 4/5, préambule 8, en-tête explicite, CRC activé.
inline float temps_air_ms(uint8_t taille_octets, uint8_t sf) {
    const float bw = 125000.0f;
    float t_sym = (float)(1UL << sf) / bw;          // durée d'un symbole (s)
    int de = (sf >= 11) ? 1 : 0;                     // low data rate optimize
    int num = 8 * taille_octets - 4 * sf + 28 + 16 - 0;
    int den = 4 * (sf - 2 * de);
    int n = (int)ceilf((float)num / den) * 5;        // CR 4/5 -> (1+4)
    if (n < 0) n = 0;
    float n_payload = 8.0f + n;
    float t_pre = (8 + 4.25f) * t_sym;
    float t_pl  = n_payload * t_sym;
    return (t_pre + t_pl) * 1000.0f;
}

struct Compteurs {
    uint8_t  sf       = 7;
    uint32_t trames   = 0;
    uint32_t octets   = 0;
    float    toa_ms   = 0.0f;
    uint32_t eveil_ms = 0;
    uint32_t _reveil  = 0;   // marqueur interne

    // Éveil : encadrer chaque cycle actif (now_ms = millis() sur ESP32).
    void reveille(uint32_t now_ms) { _reveil = now_ms; }
    void endort(uint32_t now_ms)   { eveil_ms += (now_ms - _reveil); }

    // Point d'émission unique : taille = longueur applicative de la trame.
    void emise(uint8_t taille_octets) {
        trames += 1;
        octets += taille_octets;
        toa_ms += temps_air_ms(taille_octets + OVERHEAD_LORAWAN, sf);
    }
};

// Exemple d'export série (Arduino) :
//   Serial.println("timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms");
//   Serial.printf("%lu,%s,%s,%u,%lu,%lu,%.1f,%lu\n", ts, scenario, mode,
//                 c.sf, c.trames, c.octets, c.toa_ms, c.eveil_ms);
