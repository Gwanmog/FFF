"""
Persistence layer.

Two backends, chosen by whether DATABASE_URL is set:
  - unset  -> local SQLite file (development)
  - set    -> Postgres (Neon / any managed Postgres)

Locally, DATABASE_URL and NEON_AUTH_BASE_URL come from .env.local, which
`neon deploy` / `neon env pull` write. Use the pooled DATABASE_URL (the default
one Neon writes): Streamlit holds one long-lived connection per process.

Streamlit Community Cloud has an ephemeral filesystem, so a SQLite file there is
wiped on every reboot and redeploy. Set DATABASE_URL in the Cloud secrets to keep
accounts and passport history.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import streamlit as st

try:
    from dotenv import load_dotenv

    _HERE = os.path.dirname(os.path.abspath(__file__))
    # Real environment wins, then .env.local (written by `neon env pull`), then .env.
    load_dotenv(os.path.join(_HERE, ".env.local"))
    load_dotenv(os.path.join(_HERE, ".env"))
except ImportError:
    pass

DB_PATH = os.path.join(os.path.dirname(__file__), "funky_fresh.db")

PBKDF2_ROUNDS = 240_000


def _setting(name: str) -> str:
    """Read a config value from st.secrets, falling back to the environment."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.environ.get(name, "")


def _database_url() -> str:
    url = _setting("DATABASE_URL")
    if url.startswith("postgres://"):
        # psycopg2 only accepts the postgresql:// spelling
        url = "postgresql://" + url[len("postgres://"):]
    return url


def is_postgres() -> bool:
    return bool(_database_url())


def backend_name() -> str:
    return "postgres" if is_postgres() else "sqlite"


# -- Connections ---------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _pg_connect():
    import psycopg2

    conn = psycopg2.connect(_database_url())
    conn.autocommit = True
    return conn


def _pg_live():
    """Cached Postgres connection, re-established if the server dropped it."""
    conn = _pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        _pg_connect.clear()
        conn = _pg_connect()
    return conn


@contextmanager
def _cursor():
    """Yield a cursor whose rows are keyed by column name, on either backend."""
    if is_postgres():
        import psycopg2.extras

        cur = _pg_live().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn.cursor()
            conn.commit()
        finally:
            conn.close()


def _sql(query: str) -> str:
    """Queries are written with '?'; Postgres wants '%s'."""
    return query.replace("?", "%s") if is_postgres() else query


def _query_one(query: str, params: tuple = ()):
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        return cur.fetchone()


def _query_all(query: str, params: tuple = ()) -> list:
    with _cursor() as cur:
        cur.execute(_sql(query), params)
        return cur.fetchall() or []


def _execute(query: str, params: tuple = ()) -> None:
    with _cursor() as cur:
        cur.execute(_sql(query), params)


def _integrity_errors() -> tuple:
    errors = [sqlite3.IntegrityError]
    if is_postgres():
        import psycopg2

        errors.append(psycopg2.IntegrityError)
    return tuple(errors)


# -- Schema --------------------------------------------------------------------


def init_db():
    serial = "SERIAL PRIMARY KEY" if is_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"

    _execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {serial},
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _execute(f"""
        CREATE TABLE IF NOT EXISTS user_history (
            id {serial},
            user_id INTEGER NOT NULL,
            country TEXT NOT NULL,
            visited_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrations: identity columns added after the users table first shipped.
    # neon_auth_id holds neon_auth.user.id (a UUID) for Neon Auth accounts.
    for column in ("google_id", "neon_auth_id"):
        if is_postgres():
            _execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} TEXT")
        else:
            try:
                _execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
            except sqlite3.OperationalError:
                pass  # already there
    _execute("CREATE UNIQUE INDEX IF NOT EXISTS users_neon_auth_id ON users (neon_auth_id)")


# -- Passwords -----------------------------------------------------------------
# Stored as pbkdf2_sha256$<rounds>$<salt>$<hash>. Accounts created before this
# change hold a bare SHA-256 digest and are upgraded on their next login.


def _hash_pw(password: str, salt: str = "", rounds: int = PBKDF2_ROUNDS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${digest.hex()}"


def _verify_pw(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, _ = stored.split("$", 3)
        except ValueError:
            return False
        return hmac.compare_digest(_hash_pw(password, salt, int(rounds)), stored)
    # Legacy unsalted SHA-256
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


def _is_legacy_hash(stored: str) -> bool:
    return bool(stored) and not stored.startswith("pbkdf2_sha256$")


# -- Users ---------------------------------------------------------------------


def create_user(username: str, password: str) -> bool:
    try:
        _execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, _hash_pw(password)),
        )
        return True
    except _integrity_errors():
        return False


def authenticate(username: str, password: str):
    row = _query_one(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    )
    if not row or not _verify_pw(password, row["password_hash"]):
        return None

    if _is_legacy_hash(row["password_hash"]):
        _execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_pw(password), row["id"]),
        )

    return {"id": row["id"], "username": row["username"]}


def _unique_username(name: str, email: str) -> str:
    base = name.split()[0] if name else email.split("@")[0]
    base = "".join(c for c in base if c.isalnum())[:20] or "user"
    username = base
    suffix = 1
    while _query_one("SELECT id FROM users WHERE username = ?", (username,)):
        username = f"{base}{suffix}"
        suffix += 1
    return username


def _find_or_create_external_user(column: str, external_id: str, email: str, name: str) -> dict:
    """Map an identity-provider user onto a row in our users table."""
    row = _query_one(f"SELECT id, username FROM users WHERE {column} = ?", (external_id,))
    if row:
        return {"id": row["id"], "username": row["username"]}

    username = _unique_username(name, email)
    _execute(
        f"INSERT INTO users (username, password_hash, {column}) VALUES (?, '', ?)",
        (username, external_id),
    )
    created = _query_one(f"SELECT id FROM users WHERE {column} = ?", (external_id,))
    return {"id": created["id"], "username": username}


def find_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    """Find an existing Google-linked account or create a new one."""
    return _find_or_create_external_user("google_id", google_id, email, name)


def find_or_create_neon_user(neon_auth_id: str, email: str, name: str) -> dict:
    """Find or create the app user for a Neon Auth user (neon_auth.user.id)."""
    return _find_or_create_external_user("neon_auth_id", neon_auth_id, email, name)


# -- History -------------------------------------------------------------------


def get_past_countries(user_id: int) -> list[dict]:
    rows = _query_all(
        "SELECT country, visited_at FROM user_history WHERE user_id = ? ORDER BY visited_at ASC",
        (user_id,),
    )
    return [{"country": r["country"], "visited_at": r["visited_at"]} for r in rows]


def add_country(user_id: int, country: str):
    _execute(
        "INSERT INTO user_history (user_id, country, visited_at) VALUES (?, ?, ?)",
        (user_id, country, datetime.now().isoformat()),
    )


def clear_history(user_id: int):
    _execute("DELETE FROM user_history WHERE user_id = ?", (user_id,))


def remove_country(user_id: int, country: str):
    """Remove a single country from a user's history."""
    _execute(
        "DELETE FROM user_history WHERE user_id = ? AND country = ?",
        (user_id, country),
    )
