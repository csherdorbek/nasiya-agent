"""SQLite baza: mijozlar, suhbat holati, MIB natijasi."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "nasiya.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    ig_id        TEXT PRIMARY KEY,
    state        TEXT NOT NULL DEFAULT 'new',
    model        TEXT,
    term         TEXT,
    consent_at   INTEGER,
    full_name    TEXT,
    passport     TEXT,
    pinfl        TEXT,
    phone        TEXT,
    status       TEXT NOT NULL DEFAULT 'suhbatda',
    mib_debts    TEXT,
    decision     TEXT,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);
"""

# status qiymatlari: suhbatda | mib_tekshiruvida | lead | rad | rozilik_yoq


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def get(ig_id: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM clients WHERE ig_id=?", (ig_id,)).fetchone()
        return dict(r) if r else None


def get_or_create(ig_id: str) -> dict:
    row = get(ig_id)
    if row:
        return row
    now = int(time.time())
    with conn() as c:
        c.execute(
            "INSERT INTO clients (ig_id, created_at, updated_at) VALUES (?,?,?)",
            (ig_id, now, now),
        )
    return get(ig_id)


def update(ig_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = int(time.time())
    for k in ("mib_debts",):
        if k in fields and not isinstance(fields[k], (str, type(None))):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE clients SET {cols} WHERE ig_id=?", (*fields.values(), ig_id))


def by_status(status: str) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM clients WHERE status=? ORDER BY updated_at DESC", (status,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_stale(days: int = 30) -> int:
    """Shartnoma tuzilmagan (lead bo'lmagan) mijozlar ma'lumotini o'chiradi."""
    cutoff = int(time.time()) - days * 86400
    with conn() as c:
        cur = c.execute(
            "DELETE FROM clients WHERE status!='lead' AND updated_at<?", (cutoff,)
        )
        return cur.rowcount
