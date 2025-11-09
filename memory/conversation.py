# memory/conversation.py
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any, Dict, List, Tuple

import config as cfg

# Thread-safe access for in-process usage
_lock = threading.Lock()

# One process-wide connection (SQLite is file-based; allow cross-threads)
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    db_path = cfg.settings.db_path  # ensures data dir exists
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # Pragmas tuned for concurrent reads/writes & stability
    try:
        if cfg.settings.db_wal:
            _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA synchronous=NORMAL;")
        _conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass

    _migrate(_conn)
    return _conn


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Create minimal schema if it doesn't exist.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            goal TEXT,
            mood TEXT,
            communication_style TEXT,
            response_length TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK (role IN ('user','assistant')),
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


# ---------- Public API (unchanged signatures) ----------

def get_conversation_history() -> List[Tuple[str, str]]:
    """
    Return [(role, message), ...] ordered by insertion.
    """
    conn = _connect()
    with _lock:
        cur = conn.execute(
            "SELECT role, message FROM conversation_history ORDER BY id ASC"
        )
        return [(row["role"], row["message"]) for row in cur.fetchall()]


def set_conversation_history(history: List[Tuple[str, str]]) -> None:
    """
    Replace the entire history with the provided list.
    """
    conn = _connect()
    with _lock:
        conn.execute("DELETE FROM conversation_history;")
        if history:
            conn.executemany(
                "INSERT INTO conversation_history (role, message) VALUES (?, ?);",
                history,
            )
        conn.commit()


def append_turn(role: str, message: str) -> None:
    conn = _connect()
    with _lock:
        conn.execute(
            "INSERT INTO conversation_history (role, message) VALUES (?, ?);",
            (role, message),
        )
        conn.commit()


def get_user_profile() -> Dict[str, Any]:
    """
    Return a dict of saved profile fields; empty values if not set yet.
    """
    conn = _connect()
    with _lock:
        cur = conn.execute("SELECT * FROM user_profile WHERE id = 1;")
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "name": row["name"],
            "goal": row["goal"],
            "mood": row["mood"],
            "communication_style": row["communication_style"],
            "response_length": row["response_length"],
        }


def set_user_profile(profile: Dict[str, Any]) -> None:
    """
    Upsert id=1 with given fields.
    """
    conn = _connect()
    fields = {
        "name": profile.get("name"),
        "goal": profile.get("goal"),
        "mood": profile.get("mood"),
        "communication_style": profile.get("communication_style"),
        "response_length": profile.get("response_length"),
    }
    with _lock:
        conn.execute(
            """
            INSERT INTO user_profile (id, name, goal, mood, communication_style, response_length, updated_at)
            VALUES (1, :name, :goal, :mood, :communication_style, :response_length, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                goal=excluded.goal,
                mood=excluded.mood,
                communication_style=excluded.communication_style,
                response_length=excluded.response_length,
                updated_at=CURRENT_TIMESTAMP;
            """,
            fields,
        )
        conn.commit()


def clear_conversation() -> None:
    conn = _connect()
    with _lock:
        conn.execute("DELETE FROM conversation_history;")
        conn.commit()
