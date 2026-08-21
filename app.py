"""Funky Fresh Friday — Full Immersion Date Night App"""

import os
import random
import streamlit as st
from db import init_db, create_user, authenticate, find_or_create_google_user, get_past_countries, add_country, clear_history, remove_country
from countries import COUNTRIES
from culture_data import get_music_data, get_food_data, get_movie_data
from spotify import spotify_enabled, search_country_playlists
from country_facts import get_country_facts

# ── Google OAuth helpers ────────────────────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
def _app_url() -> str:
    """
    Public base URL of this app. Google sends the user back here after login, so
    it must match an Authorized redirect URI in the Google Cloud console exactly.
    Defaults to the local dev server.
    """
    try:
        url = st.secrets.get("APP_URL", "")
    except Exception:
        url = ""
    url = url or os.environ.get("APP_URL", "")
    return (url or "http://localhost:8501").rstrip("/")


_REDIRECT_URI = _app_url()

# oauthlib refuses to run OAuth over plain HTTP unless told otherwise. That is
# fine for localhost; a real deployment is HTTPS and must keep the check on.
if _REDIRECT_URI.startswith("http://"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _google_creds():
    """Return (client_id, client_secret) from st.secrets or env vars."""
    try:
        cid = st.secrets.get("GOOGLE_CLIENT_ID", "")
        csec = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
    except Exception:
        cid, csec = "", ""
    cid = cid or os.environ.get("GOOGLE_CLIENT_ID", "")
    csec = csec or os.environ.get("GOOGLE_CLIENT_SECRET", "")
    return cid, csec


def _google_enabled() -> bool:
    cid, csec = _google_creds()
    return bool(cid and csec and not cid.startswith("your-"))


def _google_login_url() -> str:
    from requests_oauthlib import OAuth2Session
    cid, _ = _google_creds()
    oauth = OAuth2Session(cid, redirect_uri=_REDIRECT_URI, scope=_GOOGLE_SCOPES)
    auth_url, state = oauth.authorization_url(
        _GOOGLE_AUTH_URL, access_type="offline", prompt="select_account"
    )
    st.session_state.google_oauth_state = state
    return auth_url


def _handle_google_callback(code: str) -> dict:
    from requests_oauthlib import OAuth2Session
    cid, csec = _google_creds()
    state = st.session_state.get("google_oauth_state")
    oauth = OAuth2Session(cid, redirect_uri=_REDIRECT_URI, state=state)
    oauth.fetch_token(_GOOGLE_TOKEN_URL, code=code, client_secret=csec)
    return oauth.get(_GOOGLE_USERINFO_URL).json()

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Funky Fresh Friday",
    page_icon="🌍",
    layout="wide",
)

# ── Funky CSS ──────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Main background gradient */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
}
[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
}

/* Title styling */
h1 {
    background: linear-gradient(90deg, #ff6b6b, #feca57, #48dbfb, #ff9ff3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 3rem !important;
    text-align: center;
}

/* Card styling */
.culture-card {
    background: linear-gradient(145deg, #1e1e3f 0%, #2d2d5e 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.culture-card h3 {
    color: #feca57;
    margin-bottom: 0.8rem;
}
.culture-card p, .culture-card li {
    color: #e0e0e0;
}
.culture-card a {
    color: #48dbfb !important;
    text-decoration: none;
}
.culture-card a:hover {
    color: #ff6b6b !important;
    text-decoration: underline;
}

/* Country banner */
.country-banner {
    text-align: center;
    padding: 2rem;
    background: linear-gradient(145deg, #6c5ce7 0%, #a29bfe 100%);
    border-radius: 20px;
    margin: 1rem 0 2rem 0;
    box-shadow: 0 10px 40px rgba(108, 92, 231, 0.4);
}
.country-banner h2 {
    color: #ffffff;
    font-size: 2.5rem;
    margin: 0;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}
.country-banner p {
    color: #dfe6e9;
    font-size: 1.1rem;
}

/* Passport sidebar */
.passport-entry {
    background: rgba(255,255,255,0.05);
    border-left: 3px solid #feca57;
    padding: 0.4rem 0.8rem;
    margin-bottom: 0.4rem;
    border-radius: 0 8px 8px 0;
    color: #e0e0e0;
    font-size: 0.9rem;
}
/* Passport entry clickable buttons — target wide buttons in sidebar only */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"][kind="secondary"] {
    background: rgba(255,255,255,0.05) !important;
    border-left: 3px solid #feca57 !important;
    border-top: none !important;
    border-right: none !important;
    border-bottom: none !important;
    border-radius: 0 8px 8px 0 !important;
    color: #e0e0e0 !important;
    font-size: 0.85rem !important;
    font-weight: normal !important;
    text-align: left !important;
    padding: 0.4rem 0.8rem !important;
    margin-bottom: 0.2rem !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"][kind="secondary"]:hover {
    background: rgba(254, 202, 87, 0.15) !important;
    transform: none !important;
    box-shadow: none !important;
    color: #feca57 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #6c5ce7, #a29bfe) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 2rem !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
    transition: transform 0.2s !important;
}
.stButton > button:hover {
    transform: scale(1.05) !important;
    box-shadow: 0 5px 20px rgba(108, 92, 231, 0.5) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Init DB ────────────────────────────────────────────────────────────────────

init_db()

# ── Session state defaults ─────────────────────────────────────────────────────

if "user" not in st.session_state:
    st.session_state.user = None
if "current_country" not in st.session_state:
    st.session_state.current_country = None
if "show_balloons" not in st.session_state:
    st.session_state.show_balloons = False
if "google_oauth_state" not in st.session_state:
    st.session_state.google_oauth_state = None

# ── Handle Google OAuth callback ───────────────────────────────────────────────
# Google redirects back to APP_URL?code=...&state=...
_params = st.query_params
if "code" in _params and st.session_state.user is None:
    try:
        _user_info = _handle_google_callback(_params["code"])
        _user = find_or_create_google_user(
            google_id=_user_info["id"],
            email=_user_info["email"],
            name=_user_info.get("name", _user_info["email"]),
        )
        st.session_state.user = _user
        st.query_params.clear()
        st.rerun()
    except Exception as _e:
        st.query_params.clear()
        st.error(f"Google login failed: {_e}")

# ── Auth screen ────────────────────────────────────────────────────────────────


def auth_screen():
    st.markdown("# 🌍 Funky Fresh Friday")
    st.markdown(
        '<p style="text-align:center; color:#a29bfe; font-size:1.2rem;">'
        "Your passport to the world's cultures — one Friday at a time"
        "</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # ── Google OAuth button ──
        if _google_enabled():
            google_url = _google_login_url()
            st.markdown(
                f"""
                <a href="{google_url}" style="
                    display: block;
                    text-align: center;
                    background: #ffffff;
                    color: #444444;
                    padding: 0.65rem 1.5rem;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 1rem;
                    text-decoration: none;
                    margin-bottom: 1rem;
                    border: 1px solid #dadce0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                ">
                    <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
                         style="height:20px; vertical-align:middle; margin-right:10px;">
                    Continue with Google
                </a>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p style="text-align:center; color:#888; font-size:0.85rem;">— or use username/password —</p>',
                unsafe_allow_html=True,
            )

        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    user = authenticate(username, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Try again or sign up.")

        with tab_signup:
            with st.form("signup_form"):
                new_user = st.text_input("Choose a Username")
                new_pass = st.text_input("Choose a Password", type="password")
                confirm = st.text_input("Confirm Password", type="password")
                signed = st.form_submit_button("Create Account", use_container_width=True)
                if signed:
                    if not new_user or not new_pass:
                        st.error("Username and password required.")
                    elif new_pass != confirm:
                        st.error("Passwords don't match.")
                    elif create_user(new_user, new_pass):
                        st.success("Account created! Switch to Login tab.")
                    else:
                        st.error("Username already taken.")


# ── Sidebar passport ──────────────────────────────────────────────────────────


def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### 🛂 Passport — {user['username']}")
        st.markdown("---")

        history = get_past_countries(user["id"])
        visited_set = {h["country"] for h in history}

        if history:
            with st.expander(f"🗺️ {len(history)} countries visited", expanded=len(history) <= 10):
                for entry in history:
                    date_str = entry["visited_at"][:10]
                    is_active = st.session_state.current_country == entry["country"]
                    col_label, col_btn = st.columns([5, 1])
                    with col_label:
                        label = f"{'★ ' if is_active else '🌐 '}{entry['country']}\n{date_str}"
                        if st.button(label, key=f"view_{entry['country']}", use_container_width=True):
                            st.session_state.current_country = entry["country"]
                            st.rerun()
                    with col_btn:
                        if st.button("✕", key=f"rm_{entry['country']}", help=f"Remove {entry['country']}"):
                            remove_country(user["id"], entry["country"])
                            if st.session_state.current_country == entry["country"]:
                                st.session_state.current_country = None
                            st.rerun()
        else:
            st.info("No stamps yet! Hit the button to explore.")

        st.markdown("---")
        if st.button("🗑️ Clear My World History", use_container_width=True):
            clear_history(user["id"])
            st.session_state.current_country = None
            st.rerun()

        # ── Advanced ──────────────────────────────────────────────────────────
        st.markdown("---")
        with st.expander("⚙️ Advanced"):
            # ── Pick a specific country ────────────────────────────────────
            st.markdown("**Choose a specific country**")
            st.caption("Jump straight to any country, visited or not.")
            pick_search = st.text_input("Filter", placeholder="Type to filter…", key="pick_filter", label_visibility="collapsed")
            pick_options = [c for c in COUNTRIES if c.lower().startswith(pick_search.lower())] if pick_search else COUNTRIES
            picked = st.selectbox("Country", options=pick_options, index=None, placeholder="Select a country…", label_visibility="collapsed")
            if st.button("✈️ Go!", use_container_width=True, disabled=picked is None):
                if picked not in visited_set:
                    add_country(user["id"], picked)
                st.session_state.current_country = picked
                st.session_state.show_balloons = True
                st.rerun()

            st.markdown("---")

            # ── Mark as visited ────────────────────────────────────────────
            st.markdown("**Mark countries as already visited**")
            st.caption("These will be excluded from future spins.")
            remaining = [c for c in COUNTRIES if c not in visited_set]
            search = st.text_input("Filter", placeholder="Type to filter… (e.g. 'Ar')", label_visibility="collapsed")
            filtered = [c for c in remaining if c.lower().startswith(search.lower())] if search else remaining
            to_add = st.multiselect(
                "Select countries",
                options=filtered,
                placeholder="Choose countries…",
                label_visibility="collapsed",
            )
            if st.button("Add to History", use_container_width=True, disabled=not to_add):
                for c in to_add:
                    add_country(user["id"], c)
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.current_country = None
            st.rerun()


# ── Culture display ────────────────────────────────────────────────────────────


def render_culture(country: str):
    # Country banner
    st.markdown(
        f'<div class="country-banner">'
        f"<h2>🎉 {country} 🎉</h2>"
        f"<p>Tonight's destination — immerse yourself!</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Fun Facts ──
    facts = get_country_facts(country)

    def _fmt_pop(n):
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.2f}B"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    def _fmt_area(n):
        return f"{n:,.0f} km²" if n else "N/A"

    fact_rows = [
        ("🏛️ Capital", facts["capital"]),
        ("👥 Population", _fmt_pop(facts["population"]) if facts["population"] else "N/A"),
        ("📐 Area", _fmt_area(facts["area"])),
        ("🌍 Region", facts["region"]),
        ("🗣️ Languages", ", ".join(facts["languages"]) if facts["languages"] else "N/A"),
        ("💰 Currency", ", ".join(facts["currencies"]) if facts["currencies"] else "N/A"),
        ("🕌 Religion", facts["religion"]),
        ("🏆 National Sport", facts["national_sport"]),
        ("🏭 Major Industries", facts["major_industries"]),
    ]
    active_rows = [(l, v) for l, v in fact_rows if v and v != "N/A"]

    def _fact_row(label, value):
        return (
            f'<div style="display:flex;gap:6px;margin-bottom:6px;align-items:baseline;">'
            f'<span style="color:#feca57;white-space:nowrap;min-width:130px;font-size:0.85rem;">{label}</span>'
            f'<span style="color:#e0e0e0;font-size:0.85rem;">{value}</span>'
            f'</div>'
        )

    mid = (len(active_rows) + 1) // 2
    col1_html = "".join(_fact_row(l, v) for l, v in active_rows[:mid])
    col2_html = "".join(_fact_row(l, v) for l, v in active_rows[mid:])

    fun_fact_html = (
        f'<div style="margin-top:10px;padding:8px 12px;background:rgba(255,255,255,0.05);'
        f'border-radius:8px;border-left:3px solid #48dbfb;font-size:0.85rem;">'
        f'<span style="color:#48dbfb;font-weight:bold;">💡 Did you know?</span> '
        f'<span style="color:#e0e0e0;">{facts["fun_fact"]}</span>'
        f'</div>'
    ) if facts["fun_fact"] else ""

    flag = facts["flag"]
    st.markdown(
        f'<div class="culture-card">'
        f'<h3>{flag} {country} — Quick Facts</h3>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 1.5rem;">'
        f'<div>{col1_html}</div>'
        f'<div>{col2_html}</div>'
        f'</div>'
        f'{fun_fact_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # The curated facts above always render; the live ones (capital, population,
    # flag, languages, currency) can't. Say so rather than showing a thin card.
    if not facts["live_ok"]:
        st.caption(f"⚠️ Live country data unavailable — {facts['live_error']}")

    st.markdown("---")

    # Three columns for the immersion modules
    col_music, col_food, col_movies = st.columns(3)

    # ── Music ──
    with col_music:
        music = get_music_data(country)
        artists_html = "".join(f"<li>{a}</li>" for a in music["artists"]) or \
            f"<li><em>Discover {country}'s artists on Spotify!</em></li>"

        if spotify_enabled():
            playlists = search_country_playlists(country)
            if playlists:
                playlist_html = ""
                for pl in playlists:
                    img_tag = (
                        f'<img src="{pl["image"]}" style="width:48px;height:48px;'
                        f'border-radius:6px;object-fit:cover;flex-shrink:0;">'
                        if pl["image"] else ""
                    )
                    desc = pl["description"][:80] + "…" if len(pl["description"]) > 80 else pl["description"]
                    desc_tag = f'<small style="color:#aaa;">{desc}</small><br>' if desc else ""
                    playlist_html += (
                        f'<a href="{pl["url"]}" target="_blank" style="'
                        f'display:flex;align-items:center;gap:10px;'
                        f'background:rgba(255,255,255,0.05);border-radius:10px;'
                        f'padding:8px;margin-bottom:8px;text-decoration:none;'
                        f'border:1px solid rgba(255,255,255,0.08);">'
                        f'{img_tag}'
                        f'<div><strong style="color:#e0e0e0;">{pl["name"]}</strong><br>'
                        f'{desc_tag}'
                        f'<small style="color:#1DB954;">▶ {pl["tracks"]} tracks · {pl["owner"]}</small>'
                        f'</div></a>'
                    )
                st.markdown(
                    f'<div class="culture-card">'
                    f"<h3>🎵 Music — Playlists on Spotify</h3>"
                    f"<p>Artists to know: <em>{', '.join(music['artists'][:3])}</em></p>"
                    f"{playlist_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                # Spotify configured but no results — fall back
                st.markdown(
                    f'<div class="culture-card">'
                    f"<h3>🎵 Music — Spotify</h3>"
                    f"<ul>{artists_html}</ul>"
                    f'<p><a href="{music["spotify_search"]}" target="_blank">🔗 Search on Spotify</a></p>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div class="culture-card">'
                f"<h3>🎵 Music — Spotify Playlist</h3>"
                f"<p>A mix of traditional/folk and modern artists:</p>"
                f"<ul>{artists_html}</ul>"
                f'<p><a href="{music["spotify_search"]}" target="_blank">'
                f"🔗 Open 50-Song Playlist on Spotify</a></p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Food ──
    with col_food:
        dishes = get_food_data(country)
        dishes_html = ""
        for d in dishes:
            desc_tag = (
                f'<br><span style="color:#aaa;font-size:0.8rem;">{d["desc"]}</span>'
                if d.get("desc") else ""
            )
            dishes_html += (
                f'<li style="margin-bottom:10px;">'
                f'<strong>{d["name"]}</strong>{desc_tag}'
                f'<br><a href="{d["link"]}" target="_blank">Get Recipe →</a>'
                f'</li>'
            )

        st.markdown(
            f'<div class="culture-card">'
            f"<h3>🍽️ Food — Iconic Dishes</h3>"
            f"<p>Famous & national dishes to cook tonight:</p>"
            f"<ul>{dishes_html}</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Movies ──
    with col_movies:
        movies = get_movie_data(country)
        movies_html = ""
        for m in movies:
            genre_tag = (
                f'<span style="color:#a29bfe;font-size:0.78rem;"> · {m["genre"]}</span>'
                if m.get("genre") else ""
            )
            movies_html += (
                f'<li style="margin-bottom:8px;">'
                f'{m["title"]}{genre_tag}'
                f'<br><a href="{m["link"]}" target="_blank">Where to Watch →</a>'
                f'</li>'
            )

        st.markdown(
            f'<div class="culture-card">'
            f"<h3>🎬 Movies — Cinematic Connection</h3>"
            f"<p>Films from or about {country}:</p>"
            f"<ul>{movies_html}</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ── Main app ───────────────────────────────────────────────────────────────────


def main_app():
    render_sidebar()

    st.markdown("# 🌍 Funky Fresh Friday")

    user = st.session_state.user
    history = get_past_countries(user["id"])
    visited = {h["country"] for h in history}
    remaining = [c for c in COUNTRIES if c not in visited]

    # Randomizer button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if remaining:
            if st.button("🌍  Spin the Globe!", use_container_width=True):
                country = random.choice(remaining)
                add_country(user["id"], country)
                st.session_state.current_country = country
                st.session_state.show_balloons = True
                st.rerun()
        else:
            st.success("🏆 You've visited every country on Earth! What a journey!")
            if st.button("🔄 Reset and go again?", use_container_width=True):
                clear_history(user["id"])
                st.session_state.current_country = None
                st.rerun()

    # Balloons celebration
    if st.session_state.show_balloons:
        st.balloons()
        st.session_state.show_balloons = False

    # Show culture content
    if st.session_state.current_country:
        render_culture(st.session_state.current_country)
    elif history:
        # Show last visited country on reload
        st.session_state.current_country = history[-1]["country"]
        render_culture(st.session_state.current_country)


# ── Entry point ────────────────────────────────────────────────────────────────

if st.session_state.user is None:
    auth_screen()
else:
    main_app()
