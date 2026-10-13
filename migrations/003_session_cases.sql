-- Immutable creation context only. Never infer or rewrite legacy case IDs or facts.
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS session_cases (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
    payload TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES (3, '003_session_cases');
COMMIT;
