"""SQLite connection and schema for the baggage desk.

The CHECK lists below are written out on purpose. They guard the database even if a bad
value gets past the Python checks in claims.py, so they do not import from it.
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id        INTEGER PRIMARY KEY,
    passenger TEXT NOT NULL,
    flight    TEXT NOT NULL,
    type      TEXT NOT NULL CHECK (type IN ('delayed', 'lost', 'damaged')),
    tier      TEXT NOT NULL CHECK (tier IN ('standard', 'silver', 'gold')),
    status    TEXT NOT NULL
              CHECK (status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
    agent     TEXT,
    note      TEXT,
    filed_at  TEXT NOT NULL,
    deadline  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id         INTEGER PRIMARY KEY,
    claim_id   INTEGER NOT NULL REFERENCES claims (id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL
);
"""


def connect(path):
    """Open the database at path, create the tables if needed, and return the connection."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
