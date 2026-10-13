-- Additive migration: legacy schema_version remains the baseline marker (CHECK version=1).
-- schema_migrations is the ordered migration history from this release onward.
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES (1, '001_initial');
CREATE TABLE IF NOT EXISTS human_reviews (
    ticket_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    payload TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES (2, '002_human_reviews');
COMMIT;
