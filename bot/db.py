import sqlite3
import time
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Table to store LinkedIn OAuth tokens
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at REAL NOT NULL,
                refresh_expires_at REAL NOT NULL,
                org_urn TEXT
            )
        """)
        # Table to preserve state during interactive runs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                step TEXT,
                last_message_id INTEGER,
                prompt_topic TEXT,
                current_draft TEXT
            )
        """)
        # Historical logging of all successfully published posts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption TEXT NOT NULL,
                linkedin_urn TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_tokens(access_token, refresh_token, expires_in, refresh_token_expires_in, org_urn=None):
    now = time.time()
    expires_at = now + expires_in
    refresh_expires_at = now + refresh_token_expires_in
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO tokens (id, access_token, refresh_token, expires_at, refresh_expires_at, org_urn)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,
                refresh_expires_at=excluded.refresh_expires_at,
                org_urn=COALESCE(excluded.org_urn, tokens.org_urn)
        """, (access_token, refresh_token, expires_at, refresh_expires_at, org_urn))
        conn.commit()

def update_org_urn(org_urn):
    with get_db_connection() as conn:
        conn.execute("UPDATE tokens SET org_urn = ? WHERE id = 1", (org_urn,))
        conn.commit()

def get_tokens():
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE id = 1").fetchone()
        return dict(row) if row else None

def get_state():
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM state WHERE id = 1").fetchone()
        return dict(row) if row else {"step": None, "last_message_id": None, "prompt_topic": None, "current_draft": None}

def update_state(step=None, last_message_id=None, prompt_topic=None, current_draft=None):
    current = get_state()
    new_step = step if step is not None else current.get("step")
    new_msg_id = last_message_id if last_message_id is not None else current.get("last_message_id")
    new_topic = prompt_topic if prompt_topic is not None else current.get("prompt_topic")
    new_draft = current_draft if current_draft is not None else current.get("current_draft")
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO state (id, step, last_message_id, prompt_topic, current_draft)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                step=excluded.step,
                last_message_id=excluded.last_message_id,
                prompt_topic=excluded.prompt_topic,
                current_draft=excluded.current_draft
        """, (new_step, new_msg_id, new_topic, new_draft))
        conn.commit()

def reset_state():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM state WHERE id = 1")
        conn.commit()

def log_post_history(caption, linkedin_urn):
    with get_db_connection() as conn:
        conn.execute("INSERT INTO history (caption, linkedin_urn) VALUES (?, ?)", (caption, linkedin_urn))
        conn.commit()