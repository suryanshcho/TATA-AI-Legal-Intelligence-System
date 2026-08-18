import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from backend.config import settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'reviewer',
    password_hash TEXT NOT NULL,
    business_unit TEXT DEFAULT 'Corporate',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_type TEXT,
    doc_type TEXT DEFAULT 'Contract',
    business_unit TEXT DEFAULT 'Corporate',
    counterparty TEXT,
    jurisdiction TEXT,
    confidentiality TEXT DEFAULT 'Confidential',
    review_priority TEXT DEFAULT 'Normal',
    size_bytes INTEGER DEFAULT 0,
    owner_id INTEGER,
    owner_email TEXT,
    status TEXT DEFAULT 'uploaded',
    progress INTEGER DEFAULT 0,
    ocr_confidence REAL DEFAULT 0,
    stage TEXT DEFAULT 'uploaded',
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    finished_at TEXT,
    detail TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS clauses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    clause_type TEXT NOT NULL,
    clause_text TEXT,
    page INTEGER,
    section TEXT,
    involved_parties TEXT,
    obligation_owner TEXT,
    confidence REAL DEFAULT 0,
    risk_status TEXT DEFAULT 'review',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    clause_id INTEGER,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    rationale TEXT,
    evidence TEXT,
    recommendation TEXT,
    confidence REAL DEFAULT 0,
    status TEXT DEFAULT 'open',
    reviewer_action TEXT DEFAULT 'pending',
    reviewer_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version INTEGER DEFAULT 1,
    content TEXT,
    obligation_map TEXT,
    missing_clauses TEXT,
    approval_status TEXT DEFAULT 'pending',
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    actor TEXT,
    action TEXT NOT NULL,
    entity TEXT,
    detail TEXT,
    ip TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT,
    content TEXT NOT NULL,
    source TEXT,
    approved INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE(document_id, key),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
"""


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


@contextmanager
def db():
    conn = get_conn()
    depth = getattr(_local, "depth", 0)
    if depth == 0:
        try:
            conn.execute("BEGIN")
        except sqlite3.OperationalError:
            pass
    _local.depth = depth + 1
    try:
        yield conn
        _local.depth = depth
        if depth == 0:
            conn.commit()
    except Exception:
        _local.depth = depth
        if depth == 0:
            conn.rollback()
        raise


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    _seed()


def _seed():
    with db() as conn:
        cursor = conn.execute("SELECT COUNT(*) AS c FROM users")
        if cursor.fetchone()["c"] == 0:
            from backend.auth import hash_password
            conn.execute(
                "INSERT INTO users (email, name, role, password_hash, business_unit) VALUES (?,?,?,?,?)",
                (settings.ADMIN_EMAIL, "Tata Legal Admin", "admin", hash_password(settings.ADMIN_PASSWORD), "Corporate"),
            )
            conn.execute(
                "INSERT INTO users (email, name, role, password_hash, business_unit) VALUES (?,?,?,?,?)",
                ("reviewer@tata.com", "Priya Sharma", "reviewer", hash_password("tata123"), "Legal"),
            )
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ai_mode', ?)", (settings.AI_MODE,))
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('llm_model', ?)", (settings.GEMINI_MODEL,))
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_review_routing', 'high_risk')", )
