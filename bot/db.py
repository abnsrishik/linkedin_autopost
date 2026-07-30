import sqlite3
import time
import json
from dataclasses import asdict, is_dataclass
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def managed_db_connection():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with managed_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at REAL NOT NULL,
                refresh_expires_at REAL NOT NULL,
                org_urn TEXT,
                author_urn TEXT,
                author_type TEXT DEFAULT 'member'
            )
        """)
        ensure_token_column(conn, "author_urn", "TEXT")
        ensure_token_column(conn, "author_type", "TEXT DEFAULT 'member'")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                step TEXT,
                last_message_id INTEGER,
                prompt_topic TEXT,
                current_draft TEXT,
                trending_topics TEXT
            )
        """)
        ensure_state_column(conn, "trending_topics", "TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption TEXT NOT NULL,
                linkedin_urn TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


def ensure_token_column(conn, column_name, column_definition):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tokens)").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE tokens ADD COLUMN {column_name} {column_definition}")


def ensure_state_column(conn, column_name, column_definition):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(state)").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE state ADD COLUMN {column_name} {column_definition}")


def save_tokens(
    access_token,
    refresh_token,
    expires_in,
    refresh_token_expires_in,
    org_urn=None,
    author_urn=None,
    author_type="member",
):
    now = time.time()
    expires_at = now + expires_in
    refresh_expires_at = now + refresh_token_expires_in

    with managed_db_connection() as conn:
        conn.execute("""
            INSERT INTO tokens (
                id, access_token, refresh_token, expires_at, refresh_expires_at,
                org_urn, author_urn, author_type
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,
                refresh_expires_at=excluded.refresh_expires_at,
                org_urn=COALESCE(excluded.org_urn, tokens.org_urn),
                author_urn=COALESCE(excluded.author_urn, tokens.author_urn),
                author_type=COALESCE(excluded.author_type, tokens.author_type)
        """, (
            access_token,
            refresh_token,
            expires_at,
            refresh_expires_at,
            org_urn,
            author_urn,
            author_type,
        ))


def update_org_urn(org_urn):
    with managed_db_connection() as conn:
        conn.execute("UPDATE tokens SET org_urn = ? WHERE id = 1", (org_urn,))


def get_tokens():
    with managed_db_connection() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE id = 1").fetchone()
        return dict(row) if row else None


def get_state():
    with managed_db_connection() as conn:
        row = conn.execute("SELECT * FROM state WHERE id = 1").fetchone()
        if row:
            state = dict(row)
            state["trending_topics"] = _load_trending_topics(state["trending_topics"])
            return state
        return {
            "step": None,
            "last_message_id": None,
            "prompt_topic": None,
            "current_draft": None,
            "trending_topics": [],
        }


def update_state(
    step=None,
    last_message_id=None,
    prompt_topic=None,
    current_draft=None,
    trending_topics=None,
):
    current = get_state()
    new_step = step if step is not None else current.get("step")
    new_msg_id = last_message_id if last_message_id is not None else current.get("last_message_id")
    new_topic = prompt_topic if prompt_topic is not None else current.get("prompt_topic")
    new_draft = current_draft if current_draft is not None else current.get("current_draft")
    new_trending_topics = (
        trending_topics if trending_topics is not None else current.get("trending_topics", [])
    )

    with managed_db_connection() as conn:
        conn.execute("""
            INSERT INTO state (id, step, last_message_id, prompt_topic, current_draft, trending_topics)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                step=excluded.step,
                last_message_id=excluded.last_message_id,
                prompt_topic=excluded.prompt_topic,
                current_draft=excluded.current_draft,
                trending_topics=excluded.trending_topics
        """, (new_step, new_msg_id, new_topic, new_draft, json.dumps(new_trending_topics, default=_json_default)))


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _load_trending_topics(raw_value):
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def reset_state():
    with managed_db_connection() as conn:
        conn.execute("DELETE FROM state WHERE id = 1")


def log_post_history(caption, linkedin_urn):
    with managed_db_connection() as conn:
        conn.execute("INSERT INTO history (caption, linkedin_urn) VALUES (?, ?)", (caption, linkedin_urn))


def get_bot_offset():
    with managed_db_connection() as conn:
        row = conn.execute("SELECT value FROM bot_meta WHERE key = 'telegram_offset'").fetchone()
        return int(row["value"]) if row else None


def save_bot_offset(offset):
    with managed_db_connection() as conn:
        conn.execute("""
            INSERT INTO bot_meta (key, value)
            VALUES ('telegram_offset', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (str(offset),))
