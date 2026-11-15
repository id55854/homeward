"""SQLite storage: patients, messages, escalations. One file, no ORM."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    handle TEXT NOT NULL UNIQUE,        -- patient's phone (E.164) or iMessage email
    language TEXT NOT NULL DEFAULT 'English',
    letter TEXT NOT NULL,               -- discharge letter as given by the nurse
    plan TEXT NOT NULL,                 -- JSON from brain.make_plan
    day INTEGER NOT NULL DEFAULT 1,     -- day since discharge (advanced from the dashboard)
    space_id TEXT,                      -- Photon conversation, known after the first inbound message
    agent_user_id TEXT,                 -- Photon user id of our line in that conversation
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    direction TEXT NOT NULL,            -- 'in' or 'out'
    text TEXT NOT NULL,
    photon_id TEXT UNIQUE,              -- incoming Photon message id (dedupe)
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    level TEXT NOT NULL,                -- 'emergency' or 'nurse'
    reason TEXT NOT NULL,
    source TEXT NOT NULL,               -- 'rule' or 'model'
    message TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teachback (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    correct INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def q(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def x(sql: str, args: tuple = ()) -> int:
    with _lock:
        c = conn()
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def normalize_handle(handle: str) -> str:
    handle = handle.strip()
    if "@" in handle:
        return handle.lower()
    digits = "".join(ch for ch in handle if ch.isdigit())
    if handle.startswith("+"):
        return "+" + digits
    if len(digits) == 10:  # assume US number typed without country code
        return "+1" + digits
    return "+" + digits


def add_patient(name: str, handle: str, language: str, letter: str, plan: dict) -> int:
    handle = normalize_handle(handle)
    x(
        "INSERT INTO patients (name, handle, language, letter, plan, created_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(handle) DO UPDATE SET name=excluded.name, language=excluded.language, "
        "letter=excluded.letter, plan=excluded.plan, day=1",
        (name, handle, language, letter, json.dumps(plan), now()),
    )
    return q("SELECT id FROM patients WHERE handle=?", (handle,))[0]["id"]


def patient_by_handle(handle: str) -> dict | None:
    rows = q("SELECT * FROM patients WHERE handle=?", (normalize_handle(handle),))
    return _decode(rows[0]) if rows else None


def patient(pid: int) -> dict | None:
    rows = q("SELECT * FROM patients WHERE id=?", (pid,))
    return _decode(rows[0]) if rows else None


def patients() -> list[dict]:
    return [_decode(r) for r in q("SELECT * FROM patients ORDER BY id DESC")]


def _decode(row: dict) -> dict:
    row["plan"] = json.loads(row["plan"])
    return row


def seen(photon_id: str) -> bool:
    return bool(q("SELECT 1 FROM messages WHERE photon_id=?", (photon_id,)))


def add_message(pid: int, direction: str, text: str, photon_id: str | None = None) -> int:
    return x(
        "INSERT INTO messages (patient_id, direction, text, photon_id, created_at) VALUES (?,?,?,?,?)",
        (pid, direction, text, photon_id, now()),
    )


def history(pid: int, limit: int = 30) -> list[dict]:
    rows = q("SELECT * FROM messages WHERE patient_id=? ORDER BY id DESC LIMIT ?", (pid, limit))
    return list(reversed(rows))


def add_escalation(pid: int, level: str, reason: str, source: str, message: str) -> int:
    return x(
        "INSERT INTO escalations (patient_id, level, reason, source, message, created_at) VALUES (?,?,?,?,?,?)",
        (pid, level, reason, source, message, now()),
    )


def add_teachback(pid: int, question: str, answer: str, correct: bool) -> None:
    x(
        "INSERT INTO teachback (patient_id, question, answer, correct, created_at) VALUES (?,?,?,?,?)",
        (pid, question, answer, int(correct), now()),
    )
