CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO schema_version VALUES (1);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    initial_json TEXT NOT NULL,
    state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
    transaction_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    entry_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL UNIQUE REFERENCES refunds(transaction_id),
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    idempotency_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY(session_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS events (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    seq INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    PRIMARY KEY(session_id, seq)
);
CREATE TABLE IF NOT EXISTS security_events (
    event_id TEXT PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    request_id TEXT NOT NULL,
    code TEXT NOT NULL
);
