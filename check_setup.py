"""
Pre-flight check. Run this after editing secrets, and again after deploying:

    python check_setup.py            # check everything
    python check_setup.py --facts    # also probe every one of the 197 countries

It reports what is configured, what works, and for the country-facts API which
country names the upstream service does not recognise.
"""

import sys

# st.secrets works outside `streamlit run`, but Streamlit chatters about a
# missing ScriptRunContext. Quiet that so the report is readable.
import logging

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime").setLevel(logging.ERROR)

from countries import COUNTRIES  # noqa: E402
from country_facts import fetch_rest_countries, facts_api_enabled  # noqa: E402
from spotify import spotify_enabled, search_country_playlists  # noqa: E402
import db  # noqa: E402

OK = "[ok]"
WARN = "[--]"
FAIL = "[!!]"


def check_database() -> bool:
    backend = db.backend_name()
    try:
        db.init_db()
    except Exception as e:
        print(f"{FAIL} database ({backend}): {e}")
        if backend == "postgres":
            print("     check DATABASE_URL, and that psycopg2-binary is installed")
        return False

    users = db._query_one("SELECT COUNT(*) AS n FROM users")["n"]
    visits = db._query_one("SELECT COUNT(*) AS n FROM user_history")["n"]
    print(f"{OK} database ({backend}): {users} users, {visits} visits")
    if backend == "sqlite":
        print("     note: SQLite is wiped on every Streamlit Cloud reboot.")
        print("     Set DATABASE_URL to keep accounts once deployed.")
    return True


def check_facts(full: bool) -> bool:
    if not facts_api_enabled():
        print(f"{WARN} country facts: no RESTCOUNTRIES_API_KEY set")
        print("     curated facts still render; capital/population/flag will not")
        print("     free key: https://restcountries.com/sign-up")
        return False

    probe = fetch_rest_countries("Japan")
    if not probe["ok"]:
        print(f"{FAIL} country facts: {probe['error']}")
        return False
    print(f"{OK} country facts: Japan -> {probe['flag']} {probe['capital']}, "
          f"pop {probe['population']:,}")

    if not full:
        print("     run with --facts to check all 197 country names")
        return True

    print("     checking all 197 countries (this takes a minute)...")
    bad = []
    for country in COUNTRIES:
        result = fetch_rest_countries(country)
        if not result["ok"]:
            bad.append((country, result["error"]))
    if bad:
        print(f"{WARN} {len(bad)} countries did not resolve:")
        for country, error in bad:
            print(f"       {country}: {error}")
        print("     add a NAME_ALIASES entry in country_facts.py for each")
    else:
        print(f"{OK} all {len(COUNTRIES)} countries resolved")
    return not bad


def check_spotify() -> bool:
    if not spotify_enabled():
        print(f"{WARN} spotify: not configured - falls back to search links")
        return False
    results = search_country_playlists("Japan")
    if not results:
        print(f"{FAIL} spotify: credentials set but search returned nothing")
        return False
    print(f"{OK} spotify: {len(results)} playlists for Japan")
    return True


def check_google() -> bool:
    import os

    import streamlit as st

    def setting(name):
        try:
            value = st.secrets.get(name, "")
        except Exception:
            value = ""
        return value or os.environ.get(name, "")

    cid = setting("GOOGLE_CLIENT_ID")
    app_url = setting("APP_URL") or "http://localhost:8501"

    if not cid or cid.startswith("your-"):
        print(f"{WARN} google login: not configured - button is hidden")
        return False
    print(f"{OK} google login: configured, redirect URI {app_url}")
    print(f"     this must be an Authorized redirect URI in Google Cloud, exactly")
    if app_url.startswith("http://") and "localhost" not in app_url:
        print(f"{FAIL} APP_URL is plain HTTP but not localhost - Google will reject it")
        return False
    return True


def check_neon_auth() -> bool:
    """Full round trip: sign up a throwaway user, check the session, sign out, sign back in."""
    import secrets

    import neon_auth

    if not neon_auth.neon_auth_enabled():
        print(f"{WARN} neon auth: NEON_AUTH_BASE_URL not set - using local username/password")
        return False

    email = f"setup-check+{secrets.token_hex(4)}@example.com"
    password = secrets.token_urlsafe(12)
    try:
        created = neon_auth.sign_up(email, password, "Setup Check")
        if not neon_auth.get_session(created["token"]):
            raise neon_auth.NeonAuthError("new session not found by get-session")
        neon_auth.sign_out(created["token"])
        if neon_auth.get_session(created["token"]):
            raise neon_auth.NeonAuthError("session still live after sign-out")
        again = neon_auth.sign_in(email, password)
        try:
            neon_auth.sign_in(email, password + "x")
            raise neon_auth.NeonAuthError("wrong password was accepted")
        except neon_auth.NeonAuthError as e:
            if "accepted" in str(e):
                raise
        neon_auth.sign_out(again["token"])
    except neon_auth.NeonAuthError as e:
        print(f"{FAIL} neon auth: {e}")
        return False
    finally:
        if db.is_postgres():
            try:  # don't leave the throwaway user behind
                db._execute("DELETE FROM neon_auth.user WHERE email = ?", (email,))
            except Exception:
                pass
    print(f"{OK} neon auth: sign-up, session, sign-out, sign-in, bad-password all behave")
    return True


def main() -> int:
    full = "--facts" in sys.argv
    print("Funky Fresh Friday - setup check")
    print("-" * 40)

    ok_db = check_database()
    check_facts(full)
    check_spotify()
    check_google()
    check_neon_auth()

    print("-" * 40)
    if not ok_db:
        print("Database is broken - the app will not start. Fix that first.")
        return 1
    print("App can run. Anything marked [--] is an optional feature that is off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
