"""
Spotify Web API integration using Client Credentials flow.
No user login required — only app-level credentials needed.
"""

import base64
import os
import requests
import streamlit as st


def _get_creds() -> tuple[str, str]:
    try:
        cid = st.secrets.get("SPOTIFY_CLIENT_ID", "")
        csec = st.secrets.get("SPOTIFY_CLIENT_SECRET", "")
    except Exception:
        cid, csec = "", ""
    cid = cid or os.environ.get("SPOTIFY_CLIENT_ID", "")
    csec = csec or os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    return cid, csec


def spotify_enabled() -> bool:
    cid, csec = _get_creds()
    return bool(cid and csec and not cid.startswith("your-"))


@st.cache_data(ttl=3500)  # Token expires after 3600s; refresh slightly early
def _get_token() -> str:
    cid, csec = _get_creds()
    creds_b64 = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds_b64}"},
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@st.cache_data(ttl=86400)  # Cache per-country results for 24 hours
def search_country_playlists(country: str, limit: int = 5) -> list[dict]:
    """
    Search Spotify for real playlists related to a country.
    Returns up to `limit` playlist dicts with name, url, tracks, image.
    """
    try:
        token = _get_token()
    except Exception:
        return []

    # Multiple queries ranked by specificity — stop once we have enough results
    queries = [
        f"Sound of {country}",
        f"This is {country}",
        f"Best of {country}",
        f"{country} music",
        f"{country} hits",
    ]

    results = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            resp = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "playlist", "limit": 10, "market": "US"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            continue

        items = resp.json().get("playlists", {}).get("items", []) or []
        for item in items:
            if not item or item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])
            image_url = item["images"][0]["url"] if item.get("images") else None
            results.append({
                "name": item["name"],
                "description": item.get("description") or "",
                "url": item["external_urls"]["spotify"],
                "tracks": (item.get("tracks") or {}).get("total", "?"),
                "image": image_url,
                "owner": item["owner"].get("display_name", "Spotify"),
            })

        if len(results) >= limit:
            break

    return results[:limit]
