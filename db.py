import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "funky_fresh.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    # Create tables (password_hash may be empty for Google users)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            country TEXT NOT NULL,
            visited_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    # Migration: add google_id column if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.close()


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username: str, password: str) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, _hash_pw(password)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def authenticate(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
        (username, _hash_pw(password)),
    ).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "username": row["username"]}
    return None


def find_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    """Find an existing Google-linked account or create a new one."""
    conn = get_conn()
    # Try to find by google_id
    row = conn.execute(
        "SELECT id, username FROM users WHERE google_id = ?",
        (google_id,),
    ).fetchone()
    if row:
        conn.close()
        return {"id": row["id"], "username": row["username"]}

    # New Google user — derive a unique username from their name/email
    base = name.split()[0] if name else email.split("@")[0]
    base = "".join(c for c in base if c.isalnum())[:20] or "user"
    username = base
    suffix = 1
    while True:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            break
        username = f"{base}{suffix}"
        suffix += 1

    conn.execute(
        "INSERT INTO users (username, password_hash, google_id) VALUES (?, '', ?)",
        (username, google_id),
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE google_id = ?", (google_id,)
    ).fetchone()["id"]
    conn.close()
    return {"id": user_id, "username": username}


def get_past_countries(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT country, visited_at FROM user_history WHERE user_id = ? ORDER BY visited_at ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"country": r["country"], "visited_at": r["visited_at"]} for r in rows]


def add_country(user_id: int, country: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_history (user_id, country, visited_at) VALUES (?, ?, ?)",
        (user_id, country, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def clear_history(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM user_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def remove_country(user_id: int, country: str):
    """Remove a single country from a user's history."""
    conn = get_conn()
    conn.execute(
        "DELETE FROM user_history WHERE user_id = ? AND country = ?",
        (user_id, country),
    )
    conn.commit()
    conn.close()
