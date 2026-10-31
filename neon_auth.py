"""
Neon Auth (Managed Better Auth) client.

Neon ships a JS SDK only, so this talks to the branch's Better Auth REST API
directly. All calls run server-side inside Streamlit; the browser never sees
the Auth URL or the session token.

Enabled when NEON_AUTH_BASE_URL is set (`neon deploy` / `neon env pull` write
it into .env.local). Without it the app falls back to local username/password.
"""

import requests

from db import _setting

SESSION_COOKIE = "__Secure-neon-auth.session_token"
TIMEOUT = 15


class NeonAuthError(Exception):
    """A sign-in / sign-up the Auth service rejected, with a user-facing message."""


def _base_url() -> str:
    return _setting("NEON_AUTH_BASE_URL").rstrip("/")


def neon_auth_enabled() -> bool:
    return bool(_base_url())


def _headers() -> dict:
    # Better Auth checks Origin against the trusted-domain list on state-changing
    # requests; localhost is trusted by default, the deployed APP_URL must be
    # added with `neon neon-auth domain add <APP_URL>`.
    origin = (_setting("APP_URL") or "http://localhost:8501").rstrip("/")
    return {"Origin": origin}


def _post(path: str, payload: dict, token: str = "") -> tuple[dict, str]:
    """POST to the Auth API. Returns (json body, signed session cookie if one was set)."""
    cookies = {SESSION_COOKIE: token} if token else None
    try:
        r = requests.post(
            _base_url() + path, json=payload, headers=_headers(),
            cookies=cookies, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise NeonAuthError(f"Could not reach the auth service: {e}") from e
    try:
        body = r.json() or {}
    except ValueError:
        body = {}
    if not r.ok:
        raise NeonAuthError(body.get("message") or f"Auth service returned HTTP {r.status_code}")
    return body, r.cookies.get(SESSION_COOKIE, "")


def _result(response: tuple[dict, str]) -> dict:
    # The session credential is the *signed* cookie value (token.signature), not
    # the bare "token" in the JSON body: Better Auth rejects an unsigned cookie.
    body, cookie = response
    user = body.get("user") or {}
    if not cookie or not user.get("id"):
        raise NeonAuthError("Auth service returned no session")
    return {
        "token": cookie,
        "id": user["id"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
    }


def sign_up(email: str, password: str, name: str) -> dict:
    """Create an account. Returns {token, id, email, name}; the user is signed in."""
    return _result(_post("/sign-up/email", {"email": email, "password": password, "name": name}))


def sign_in(email: str, password: str) -> dict:
    """Returns {token, id, email, name}. Raises NeonAuthError on bad credentials."""
    return _result(_post("/sign-in/email", {"email": email, "password": password}))


def get_session(token: str):
    """The live session for a token, or None if it expired or was revoked."""
    try:
        r = requests.get(
            _base_url() + "/get-session", headers=_headers(),
            cookies={SESSION_COOKIE: token}, timeout=TIMEOUT,
        )
        body = r.json() if r.ok else None
    except (requests.RequestException, ValueError):
        return None
    return body if body and body.get("session") else None


def sign_out(token: str) -> None:
    try:
        _post("/sign-out", {}, token)
    except NeonAuthError:
        pass  # already expired / revoked: nothing left to end
