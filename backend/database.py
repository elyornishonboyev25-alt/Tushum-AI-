"""SQLite persistence with explicit, atomic write transactions."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

DEFAULT_DATABASE = Path(__file__).parent / "data" / "tushum.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
CREATE TABLE IF NOT EXISTS businesses (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, sector TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner','manager','viewer')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY, identifier TEXT NOT NULL, attempted_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(identifier, attempted_at);
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL, phone TEXT NOT NULL, company TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '', contact_allowed INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customer_business ON customers(business_id, phone);
CREATE TABLE IF NOT EXISTS debts (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    customer_id TEXT NOT NULL REFERENCES customers(id), title TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0), issued_on TEXT NOT NULL, due_on TEXT NOT NULL,
    reference TEXT, note TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(business_id, reference)
);
CREATE INDEX IF NOT EXISTS idx_debt_business ON debts(business_id, customer_id, due_on);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    debt_id TEXT NOT NULL REFERENCES debts(id), amount INTEGER NOT NULL CHECK (amount > 0),
    paid_on TEXT NOT NULL, method TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    recorded_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_business ON payments(business_id, debt_id, paid_on);
CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    payment_id TEXT NOT NULL REFERENCES payments(id), amount INTEGER NOT NULL CHECK (amount > 0),
    refunded_on TEXT NOT NULL, reason TEXT NOT NULL,
    recorded_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refund_payment ON refunds(payment_id);
CREATE TABLE IF NOT EXISTS promises (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    debt_id TEXT NOT NULL REFERENCES debts(id), amount INTEGER NOT NULL CHECK (amount > 0),
    due_on TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', cancelled INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promise_business ON promises(business_id, debt_id, due_on);
CREATE TABLE IF NOT EXISTS promise_allocations (
    id TEXT PRIMARY KEY, payment_id TEXT NOT NULL REFERENCES payments(id),
    promise_id TEXT NOT NULL REFERENCES promises(id), amount INTEGER NOT NULL,
    reversed_amount INTEGER NOT NULL DEFAULT 0,
    CHECK (amount > 0 AND reversed_amount >= 0 AND reversed_amount <= amount)
);
CREATE INDEX IF NOT EXISTS idx_allocation_promise ON promise_allocations(promise_id);
CREATE INDEX IF NOT EXISTS idx_allocation_payment ON promise_allocations(payment_id);
CREATE TABLE IF NOT EXISTS disputes (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    debt_id TEXT NOT NULL REFERENCES debts(id), reason TEXT NOT NULL,
    resolution TEXT NOT NULL DEFAULT '', resolved INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    user_id TEXT NOT NULL REFERENCES users(id), customer_id TEXT REFERENCES customers(id),
    debt_id TEXT REFERENCES debts(id), kind TEXT NOT NULL, title TEXT NOT NULL,
    details TEXT NOT NULL, amount INTEGER, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_business ON events(business_id, created_at DESC);
CREATE TABLE IF NOT EXISTS notification_reads (
    user_id TEXT NOT NULL REFERENCES users(id), notification_key TEXT NOT NULL,
    PRIMARY KEY(user_id, notification_key)
);
CREATE TABLE IF NOT EXISTS operations (
    business_id TEXT NOT NULL REFERENCES businesses(id), operation_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL,
    payload_hash TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(business_id, operation_id)
);
CREATE TABLE IF NOT EXISTS imports (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    file_hash TEXT NOT NULL, filename TEXT NOT NULL, headers TEXT NOT NULL,
    rows_json TEXT NOT NULL, committed INTEGER NOT NULL DEFAULT 0,
    result_json TEXT, created_at TEXT NOT NULL,
    UNIQUE(business_id, file_hash)
);
CREATE TABLE IF NOT EXISTS sms_messages (
    id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
    customer_id TEXT NOT NULL REFERENCES customers(id), user_id TEXT NOT NULL REFERENCES users(id),
    phone TEXT NOT NULL, sender TEXT NOT NULL, text TEXT NOT NULL, payload TEXT NOT NULL,
    account_key TEXT NOT NULL, status TEXT NOT NULL, provider_id TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL CHECK(price >= 0), parts INTEGER NOT NULL CHECK(parts > 0),
    error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sms_customer ON sms_messages(business_id,customer_id,created_at DESC);
"""


def database_path() -> Path:
    return Path(os.environ.get("TUSHUM_DATABASE", str(DEFAULT_DATABASE))).resolve()


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize() -> None:
    with read() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
        if version != 1:
            raise RuntimeError("Database schema version is unsupported. Back up before migrating.")


@contextmanager
def read():
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def write():
    with read() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
