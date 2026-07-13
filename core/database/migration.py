"""Schema migration support."""
from __future__ import annotations

EPISODIC_SCHEMA = '''CREATE TABLE IF NOT EXISTS episodic_memories (
    id TEXT PRIMARY KEY, memory_type TEXT NOT NULL DEFAULT 'episodic',
    content TEXT NOT NULL DEFAULT '{}', importance REAL NOT NULL DEFAULT 0.5,
    embedding TEXT, timestamp TEXT NOT NULL, ttl INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ep_imp ON episodic_memories(importance);
CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodic_memories(timestamp);
'''

SEMANTIC_SCHEMA = '''CREATE TABLE IF NOT EXISTS semantic_memories (
    id TEXT PRIMARY KEY, memory_type TEXT NOT NULL DEFAULT 'semantic',
    content TEXT NOT NULL DEFAULT '{}', importance REAL NOT NULL DEFAULT 0.5,
    embedding TEXT, timestamp TEXT NOT NULL, ttl INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sem_imp ON semantic_memories(importance);
'''

DECISION_SCHEMA = '''CREATE TABLE IF NOT EXISTS decision_memories (
    id TEXT PRIMARY KEY, memory_type TEXT NOT NULL DEFAULT 'decision',
    content TEXT NOT NULL DEFAULT '{}', importance REAL NOT NULL DEFAULT 0.5,
    embedding TEXT, timestamp TEXT NOT NULL, ttl INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dec_imp ON decision_memories(importance);
'''

AUDIT_SCHEMA = '''CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL,
    operation TEXT NOT NULL, timestamp TEXT NOT NULL,
    agent_id TEXT, trace_id TEXT, details TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_mem ON audit_log(memory_id);
'''

SNAPSHOT_SCHEMA = '''CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY, label TEXT,
    timestamp TEXT NOT NULL, data TEXT NOT NULL
);
'''

SCHEMAS = {
    "episodic": EPISODIC_SCHEMA,
    "semantic": SEMANTIC_SCHEMA,
    "decision": DECISION_SCHEMA,
    "audit": AUDIT_SCHEMA,
    "snapshot": SNAPSHOT_SCHEMA,
}

def run_migration(db_name, db_manager):
    schema = SCHEMAS.get(db_name)
    if schema:
        conn = db_manager.get_connection(db_name)
        conn.executescript(schema)
        conn.commit()

def run_all_migrations(db_manager):
    for name in SCHEMAS:
        run_migration(name, db_manager)