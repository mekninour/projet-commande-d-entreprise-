// emulateur/test/banc_pc.cpp
// -----------------------------------------------------------------------------
// Banc PC de l'émulateur (B3) : la boucle du firmware ESP32, sans la radio.
//
//   lire mesure (E4) -> doit_emettre (E5) -> encoder_trame (E1) -> emettre +
//   compteurs (E6) -> export CSV
//
// Même code que le futur firmware : seules la lecture du scénario (fichier CSV
// au lieu de la flash) et l'émission (comptage au lieu de la radio) changent.
// Décisions appliquées : document « B3 – Décisions émulateur avant le 16/11 ».
//
// Usage :
//   ./banc <scenario.csv> [naif|fixe|s4|tous] [--sf N] [--radio lorawan|p2p]
//          [--reglage defaut|s4-regle|r3] [--periode-fixe S] [--s4-delta MM]
//          [--s4-calme S] [--s4-alerte S] [--seuil MM] [--hex] [--entete]
//   ./banc --test-v12      (vérifie la trame de test du contrat v1.2)
//
// Réglages nommés (--reglage) :
//   defaut    valeurs par défaut de modes.h (S4 : calme 1 h, alerte 15 min,
//             variation 50 mm)
//   s4-regle  réglage présenté au client le 16/11 (S4 : calme 2 h,
//             alerte 30 min, variation 100 mm)
//   r3        hypothèses de la simulation R3 de Gaetan (S4 : calme 1 h,
//             alerte 10 min, variation 100 mm)
// Les options --s4-* placées après --reglage le complètent ou le modifient.
// -----------------------------------------------------------------------------
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vector>

#include "mesure.h"
#include "modes.h"
#include "compteurs.h"

// Encodeur E1 (Gaetan), écrit en C : trame/encodeur/encodeur.c
extern "C" {
#include "encodeur.h"
}

static const uint16_t NODE_ID       = 3;     // nœud émulé (0 interdit, règle 1)
static const uint8_t  BATT_INCONNUE = 0xFF;  // contrat v1.2 : tension inconnue
static const uint8_t  STATUS_ALERTE = 0x01;  // contrat v1.2 : bit 0
static const uint8_t  TAILLE_TRAME  = 12;

// --- E4 : lecture du scénario (sur ESP32 : tableau en flash) -----------------
static uint32_t epoch_iso(const char* s) {            // "AAAA-MM-JJTHH:MM:SSZ"
    struct tm t; memset(&t, 0, sizeof t);
    if (sscanf(s, "%d-%d-%dT%d:%d:%d", &t.tm_year, &t.tm_mon, &t.tm_mday,
               &t.tm_hour, &t.tm_min, &t.tm_sec) != 6) return 0;
    t.tm_year -= 1900; t.tm_mon -= 1;
    return (uint32_t)timegm(&t);
}

static bool lire_scenario(const char* chemin, std::vector<Mesure>& v) {
    FILE* f = fopen(chemin, "r");
    if (!f) { perror(chemin); return false; }
    char ligne[256];
    while (fgets(ligne, sizeof ligne, f)) {
        unsigned long t_s, h; char date[32];
        if (sscanf(ligne, "%lu;%31[^;];%lu", &t_s, date, &h) != 3) continue; // en-tête
        Mesure m;
        m.t_s = (uint32_t)t_s;
        m.horodatage = epoch_iso(date);
        m.hauteur_mm = (h > 0xFFFF) ? MESURE_INVALIDE : (uint16_t)h;
        v.push_back(m);
    }
    fclose(f);
    return !v.empty();
}

// --- Témoin d'alerte (D5) -----------------------------------------------------
// Même règle que le mode S4 (modes.cpp) : seuil absolu seuil_alerte_mm s'il est
// renseigné (--seuil), sinon plus basse hauteur vue + marge ; hystérésis.
// Sert de référence commune aux 3 modes pour le bit 0 et le retard d'alerte.
struct Temoin {
    uint16_t base = MESURE_INVALIDE;
    bool en_alerte = false;
    void voir(const Mesure& m, const ParamsModes& p) {
        if (!m.valide()) return;
        if (m.hauteur_mm < base) base = m.hauteur_mm;
        uint32_t seuil = p.seuil_alerte_mm ? (uint32_t)p.seuil_alerte_mm
                                           : (uint32_t)base + p.s4_marge_alerte_mm;
        if (!en_alerte && m.hauteur_mm >= seuil) en_alerte = true;
        else if (en_alerte && (uint32_t)m.hauteur_mm + p.s4_hysteresis_mm < seuil)
            en_alerte = false;
    }
};

// next_min (D6) : période courante du mode (modes.cpp), ramenée à 1..254 min.
static uint8_t next_min_trame(const EtatMode& e) {
    uint32_t mn = periode_courante_min(e);
    return (uint8_t)(mn < 1 ? 1 : (mn > 254 ? 254 : mn));
}

// Réglages nommés : un seul endroit pour les valeurs présentées au client.
static bool appliquer_reglage(const char* nom, ParamsModes& p) {
    if (!strcmp(nom, "defaut")) { return true; }
    if (!strcmp(nom, "r3")) {           // hypothèses de la simulation R3 (Gaetan)
        p.s4_periode_calme_s  = 3600;   // 1 trame / h au calme
        p.s4_periode_alerte_s = 600;    // 1 trame / 10 min en alerte
        p.s4_delta_mm         = 100;    // envoi si l'eau varie de 10 cm
        return true;
    }
    if (!strcmp(nom, "s4-regle")) {
        p.s4_periode_calme_s  = 7200;   // 1 trame / 2 h au calme
        p.s4_periode_alerte_s = 1800;   // 1 trame / 30 min en alerte
        p.s4_delta_mm         = 100;    // envoi immédiat si l'eau varie de 10 cm
        return true;
    }
    return false;
}

// --- Une campagne : un scénario, un mode --------------------------------------
static void campagne(const std::vector<Mesure>& v, const char* scenario, Mode mode,
                     const ParamsModes& p, uint8_t sf, uint8_t entete, bool hex) {
    EtatMode e; init_etat(e, mode, p);
    Compteurs c; c.sf = sf; c.entete = entete;
    Temoin tem;
    uint16_t seq = 0;
    long t_franchi = -1;

    for (size_t i = 0; i < v.size(); ++i) {
        const Mesure& m = v[i];
        bool avant = tem.en_alerte;
        tem.voir(m, p);
        if (tem.en_alerte && !avant && t_franchi < 0) t_franchi = m.t_s;

        if (!doit_emettre(m, e)) continue;           // D2 : toutes les mesures

        // emettre(trame) : point d'émission unique (D1)
        bool alerte = (mode == Mode::S4) ? e.en_alerte : tem.en_alerte;
        uint8_t trame[TAILLE_TRAME];
        seq = (uint16_t)(seq + 1);                    // D6 : seq géré à l'émission
        encoder_trame(NODE_ID, m.hauteur_mm, BATT_INCONNUE, seq,
                      alerte ? STATUS_ALERTE : 0, next_min_trame(e), trame);
        c.emise(TAILLE_TRAME);
        if (alerte && t_franchi >= 0 && c.retard_alerte_s < 0)
            c.retard_alerte_s = (int32_t)(m.t_s - t_franchi);

        if (hex) {
            fprintf(stderr, "%s %-4s t+%7lus ", scenario, nom_mode(mode),
                    (unsigned long)m.t_s);
            for (int k = 0; k < TAILLE_TRAME; ++k) fprintf(stderr, "%02X ", trame[k]);
            fprintf(stderr, "\n");
        }
    }

    // Export (8 colonnes figées + retard_alerte_s). eveil_ms : 0 sur PC
    // (mesuré avec millis() sur l'ESP32 seulement).
    time_t now = time(NULL); char ts[32];
    strftime(ts, sizeof ts, "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
    printf("%s,%s,%s,%u,%lu,%lu,%.1f,%lu,", ts, scenario, nom_mode(mode), c.sf,
           (unsigned long)c.trames, (unsigned long)c.octets, c.toa_ms,
           (unsigned long)c.eveil_ms);
    if (c.retard_alerte_s >= 0) printf("%ld", (long)c.retard_alerte_s);
    printf("\n");
}

static int test_v12() {
    // Contrat v1.2, section 8 : nœud 3, 310 mm, 3,15 V, seq 157, alerte, 5 min.
    const uint8_t attendu[TAILLE_TRAME] =
        {0x00,0x03,0x01,0x36,0x82,0x00,0x9D,0x01,0x05,0x00,0x00,0x00};
    uint8_t t[TAILLE_TRAME];
    encoder_trame(3, 310, 0x82, 157, STATUS_ALERTE, 5, t);
    bool ok = memcmp(t, attendu, TAILLE_TRAME) == 0;
    printf("Trame v1.2 : ");
    for (int k = 0; k < TAILLE_TRAME; ++k) printf("%02X ", t[k]);
    printf("-> %s\n", ok ? "OK (identique au contrat)" : "ERREUR");
    return ok ? 0 : 1;
}

int main(int argc, char** argv) {
    if (argc >= 2 && strcmp(argv[1], "--test-v12") == 0) return test_v12();
    if (argc < 2) {
        fprintf(stderr, "usage : %s <scenario.csv> [naif|fixe|s4|tous] [--sf N] "
                "[--radio lorawan|p2p] [--reglage defaut|s4-regle|r3] [--periode-fixe S] "
                "[--s4-delta MM] [--s4-calme S] [--s4-alerte S] [--seuil MM] [--hex] [--entete]\n"
                "        %s --test-v12\n", argv[0], argv[0]);
        return 2;
    }
    const char* chemin = argv[1];
    const char* choix = "tous";
    uint8_t sf = 10, entete = ENTETE_LORAWAN;
    bool hex = false, avec_entete = false;
    ParamsModes p;                                  // fixe : 1800 s (D3, contrat)

    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--sf") && i + 1 < argc) sf = (uint8_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--radio") && i + 1 < argc) {
            ++i; entete = !strcmp(argv[i], "p2p") ? ENTETE_P2P : ENTETE_LORAWAN;
        }
        else if (!strcmp(argv[i], "--reglage") && i + 1 < argc) {
            ++i;
            if (!appliquer_reglage(argv[i], p)) {
                fprintf(stderr, "réglage inconnu : %s (defaut, s4-regle, r3)\n", argv[i]);
                return 2;
            }
        }
        else if (!strcmp(argv[i], "--seuil") && i + 1 < argc)
            p.seuil_alerte_mm = (uint16_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--periode-fixe") && i + 1 < argc)
            p.periode_fixe_s = (uint32_t)atol(argv[++i]);
        else if (!strcmp(argv[i], "--s4-delta") && i + 1 < argc)
            p.s4_delta_mm = (uint16_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--s4-calme") && i + 1 < argc)
            p.s4_periode_calme_s = (uint32_t)atol(argv[++i]);
        else if (!strcmp(argv[i], "--s4-alerte") && i + 1 < argc)
            p.s4_periode_alerte_s = (uint32_t)atol(argv[++i]);
        else if (!strcmp(argv[i], "--hex")) hex = true;
        else if (!strcmp(argv[i], "--entete")) avec_entete = true;
        else choix = argv[i];
    }

    std::vector<Mesure> v;
    if (!lire_scenario(chemin, v)) return 1;
    const char* base = strrchr(chemin, '/'); base = base ? base + 1 : chemin;
    char scenario[64]; snprintf(scenario, sizeof scenario, "%s", base);
    char* pt = strrchr(scenario, '.'); if (pt) *pt = 0;

    if (avec_entete)
        printf("timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s\n");

    Mode modes[3] = {Mode::NAIF, Mode::FIXE, Mode::S4};
    for (int k = 0; k < 3; ++k) {
        if (strcmp(choix, "tous") && strcmp(choix, nom_mode(modes[k]))) continue;
        campagne(v, scenario, modes[k], p, sf, entete, hex);
    }
    return 0;
}
