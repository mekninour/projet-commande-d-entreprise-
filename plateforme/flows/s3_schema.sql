-- S3 : schéma de la base (créé au démarrage s'il n'existe pas)
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS mesures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     INTEGER NOT NULL,
    received_at TEXT    NOT NULL,   -- heure de réception, ISO 8601 UTC (règle 4)
    water_mm    INTEGER,            -- NULL = mesure invalide (0xFFFF)
    water_valid INTEGER NOT NULL,   -- 1 / 0
    batt_v      REAL,               -- NULL = inconnue (0xFF)
    seq         INTEGER NOT NULL,
    alert       INTEGER NOT NULL,   -- bit d'alerte du nœud (1 / 0)
    next_min    INTEGER,            -- NULL = inconnu (0xFF)
    lost_before INTEGER NOT NULL DEFAULT 0,
    rssi        INTEGER,
    snr         REAL,
    source      TEXT,
    payload_hex TEXT,
    UNIQUE (node_id, received_at, seq)
);
CREATE INDEX IF NOT EXISTS idx_mesures_capteur_heure ON mesures (node_id, received_at);
CREATE TABLE IF NOT EXISTS evenements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    type        TEXT NOT NULL,      -- trames_perdues, doublon, rejet, retour_seq
    node_id     INTEGER,
    seq         INTEGER,
    details     TEXT                -- le message complet, en JSON
);
CREATE INDEX IF NOT EXISTS idx_evenements_heure ON evenements (received_at);
