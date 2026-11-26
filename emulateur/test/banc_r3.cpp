// emulateur/test/banc_r3.cpp
// Copie de banc_pc.cpp intégrant la conservation côté nœud et le rattrapage
// étalé (tâche R3) via la librairie rattrapage_r3.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vector>

#include "mesure.h"
#include "modes.h"
#include "compteurs.h"
#include "rattrapage_r3.h"

extern "C" {
#include "encodeur.h"
}

static const uint16_t NODE_ID       = 3;
static const uint8_t  BATT_INCONNUE = 0xFF;
static const uint8_t  STATUS_ALERTE = 0x01;
static const uint8_t  TAILLE_TRAME  = 12;

struct ConfigR3 {
    bool     coupure_active = false;
    uint32_t coupure_debut  = 0;
    uint32_t coupure_fin    = 0;
    ParamsR3 params;
};

static uint32_t epoch_iso(const char* s) {
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
        if (sscanf(ligne, "%lu;%31[^;];%lu", &t_s, date, &h) != 3) continue;
        Mesure m;
        m.t_s = (uint32_t)t_s;
        m.horodatage = epoch_iso(date);
        m.hauteur_mm = (h > 0xFFFF) ? MESURE_INVALIDE : (uint16_t)h;
        v.push_back(m);
    }
    fclose(f);
    return !v.empty();
}

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

static uint8_t next_min_trame(const EtatMode& e) {
    uint32_t mn = periode_courante_min(e);
    return (uint8_t)(mn < 1 ? 1 : (mn > 254 ? 254 : mn));
}

static bool appliquer_reglage(const char* nom, ParamsModes& p) {
    if (!strcmp(nom, "defaut")) { return true; }
    if (!strcmp(nom, "r3")) {
        p.s4_periode_calme_s  = 3600;
        p.s4_periode_alerte_s = 900;
        p.s4_delta_mm         = 100;
        return true;
    }
    if (!strcmp(nom, "s4-regle")) {
        p.s4_periode_calme_s  = 7200;
        p.s4_periode_alerte_s = 1800;
        p.s4_delta_mm         = 100;
        return true;
    }
    return false;
}

static bool radio_ok(const ConfigR3& cfg, uint32_t t_s) {
    if (!cfg.coupure_active) return true;
    return !(t_s >= cfg.coupure_debut && t_s < cfg.coupure_fin);
}

static void campagne(const std::vector<Mesure>& v, const char* scenario, Mode mode,
                     const ParamsModes& p, const ConfigR3& cfg_r3,
                     uint8_t sf, uint8_t entete, bool hex, bool regroupement) {
    EtatMode e; init_etat(e, mode, p);
    EtatR3 r3; r3_init(r3, cfg_r3.params);
    Compteurs c; c.sf = sf; c.entete = entete;
    Temoin tem;
    uint16_t seq = 0;
    long t_franchi = -1;

    for (size_t i = 0; i < v.size(); ++i) {
        const Mesure& m = v[i];
        bool avant = tem.en_alerte;
        tem.voir(m, p);
        if (tem.en_alerte && !avant && t_franchi < 0) t_franchi = m.t_s;

        bool dispo = radio_ok(cfg_r3, m.t_s);
        uint8_t emis_ce_cycle = 0;
        bool s4 = (mode == Mode::S4 || mode == Mode::S4V1);

        if (decider_emission(m, e)) {
            bool alerte = s4 ? e.en_alerte : tem.en_alerte;
            seq = (uint16_t)(seq + 1);
            if (dispo) {
                uint8_t trame[TAILLE_TRAME];
                encoder_trame(NODE_ID, m.hauteur_mm, BATT_INCONNUE, seq,
                              alerte ? STATUS_ALERTE : 0, next_min_trame(e), trame);
                if (regroupement && mode == Mode::S4 && m.valide()) {
                    int8_t ec[3];
                    ecarts_regroupement(e, m.hauteur_mm, ec);
                    for (int k = 0; k < 3; ++k) trame[9 + k] = (uint8_t)ec[k];
                }
                confirmer_envoi(m, e);
                c.emise(TAILLE_TRAME);
                emis_ce_cycle++;
                if (alerte && t_franchi >= 0 && c.retard_alerte_s < 0)
                    c.retard_alerte_s = (int32_t)(m.t_s - t_franchi);

                if (hex) {
                    fprintf(stderr, "%s %-4s %-9s t+%7lus LIVE ", scenario, nom_mode(mode),
                            mode == Mode::S4 ? nom_etat_s4(e.etat_s4) : "", (unsigned long)m.t_s);
                    for (int k = 0; k < TAILLE_TRAME; ++k) fprintf(stderr, "%02X ", trame[k]);
                    fprintf(stderr, "\n");
                }
            } else {
                r3_empiler(r3, m, seq);
                confirmer_envoi(m, e);
                if (hex) {
                    fprintf(stderr, "%s %-4s %-9s t+%7lus BUFFERED(seq=%u, tam=%u)\n",
                            scenario, nom_mode(mode),
                            mode == Mode::S4 ? nom_etat_s4(e.etat_s4) : "",
                            (unsigned long)m.t_s, (unsigned)seq, (unsigned)r3_taille(r3));
                }
            }
        }

        EntreeR3 entree;
        while (dispo && r3_peut_rattraper(r3, m.t_s, emis_ce_cycle)) {
            if (!r3_depiler(r3, m.t_s, entree)) break;
            bool alerte_r = s4 ? e.en_alerte : tem.en_alerte;
            uint8_t st = alerte_r ? STATUS_ALERTE : 0;

            uint8_t trame[TAILLE_TRAME];
            encoder_trame(NODE_ID, entree.mesure.hauteur_mm, BATT_INCONNUE, entree.seq_origine,
                          st, next_min_trame(e), trame);
            c.emise(TAILLE_TRAME);
            emis_ce_cycle++;

            if (hex) {
                fprintf(stderr, "%s %-4s %-9s t+%7lus RATTR(seq=%u, t+%lu) ", scenario, nom_mode(mode),
                        mode == Mode::S4 ? nom_etat_s4(e.etat_s4) : "",
                        (unsigned long)m.t_s, (unsigned)entree.seq_origine, (unsigned long)entree.mesure.t_s);
                for (int k = 0; k < TAILLE_TRAME; ++k) fprintf(stderr, "%02X ", trame[k]);
                fprintf(stderr, "\n");
            }
        }
    }

    if (cfg_r3.coupure_active || hex) {
        fprintf(stderr, "[R3 %s/%s] ajoutes=%lu rattrapes=%lu ecrases=%lu restants=%u\n",
                scenario, nom_mode(mode), (unsigned long)r3.total_ajoutes,
                (unsigned long)r3.total_rattrapes, (unsigned long)r3.total_ecrases,
                (unsigned)r3_taille(r3));
    }

    time_t now = time(NULL); char ts[32];
    strftime(ts, sizeof ts, "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
    printf("%s,%s,%s,%u,%lu,%lu,%.1f,%lu,", ts, scenario, nom_mode(mode), c.sf,
           (unsigned long)c.trames, (unsigned long)c.octets, c.toa_ms,
           (unsigned long)c.eveil_ms);
    if (c.retard_alerte_s >= 0) printf("%ld", (long)c.retard_alerte_s);
    printf(",%lu\n", (unsigned long)e.nb_mesures);
}

static int test_v12() {
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
        fprintf(stderr, "usage : %s <scenario.csv> [naif|fixe|s4|s4v1|tous] [--sf N] "
                "[--radio lorawan|p2p] [--reglage defaut|s4-regle|r3] [--periode-fixe S] "
                "[--s4-delta MM] [--s4-calme S] [--s4-alerte S] [--seuil MM] "
                "[--r3-coupure DEBUT:FIN] [--r3-cap N] [--r3-max-cycle N] [--r3-delai S] "
                "[--regroupement] [--hex] [--entete]\n"
                "        %s --test-v12\n", argv[0], argv[0]);
        return 2;
    }
    const char* chemin = argv[1];
    const char* choix = "tous";
    uint8_t sf = 10, entete = ENTETE_LORAWAN;
    bool hex = false, avec_entete = false, regroupement = false;
    ParamsModes p;
    ConfigR3 cfg_r3;

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
        else if (!strcmp(argv[i], "--r3-coupure") && i + 1 < argc) {
            unsigned long d = 0, f = 0;
            if (sscanf(argv[++i], "%lu:%lu", &d, &f) == 2 && f > d) {
                cfg_r3.coupure_active = true;
                cfg_r3.coupure_debut  = (uint32_t)d;
                cfg_r3.coupure_fin    = (uint32_t)f;
            } else {
                fprintf(stderr, "format --r3-coupure attendu : DEBUT:FIN (avec FIN > DEBUT)\n");
                return 2;
            }
        }
        else if (!strcmp(argv[i], "--r3-cap") && i + 1 < argc)
            cfg_r3.params.capacite_max = (uint16_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--r3-max-cycle") && i + 1 < argc)
            cfg_r3.params.max_par_cycle = (uint8_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--r3-delai") && i + 1 < argc)
            cfg_r3.params.delai_min_s = (uint32_t)atol(argv[++i]);
        else if (!strcmp(argv[i], "--hex")) hex = true;
        else if (!strcmp(argv[i], "--regroupement")) regroupement = true;
        else if (!strcmp(argv[i], "--entete")) avec_entete = true;
        else choix = argv[i];
    }

    std::vector<Mesure> v;
    if (!lire_scenario(chemin, v)) return 1;
    const char* base = strrchr(chemin, '/'); base = base ? base + 1 : chemin;
    char scenario[64]; snprintf(scenario, sizeof scenario, "%s", base);
    char* pt = strrchr(scenario, '.'); if (pt) *pt = 0;

    if (avec_entete)
        printf("timestamp,scenario,mode,sf,trames,octets,toa_ms,eveil_ms,retard_alerte_s,mesures\n");

    Mode modes[4] = {Mode::NAIF, Mode::FIXE, Mode::S4, Mode::S4V1};
    bool trouve = false;
    for (int k = 0; k < 4; ++k) {
        if (strcmp(choix, "tous") && strcmp(choix, nom_mode(modes[k]))) continue;
        trouve = true;
        campagne(v, scenario, modes[k], p, cfg_r3, sf, entete, hex, regroupement);
    }
    if (!trouve) { fprintf(stderr, "mode inconnu : %s\n", choix); return 2; }
    return 0;
}