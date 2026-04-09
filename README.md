# 🌍 Funky Fresh Friday

A cultural immersion app for date nights. Spin the globe and get dropped into a random country — with music, food recipes, and movies to match.

## What it does

- **Spin the Globe** — randomly picks a country you haven't visited yet
- **Music** — artists to know + Spotify playlist links (live search if Spotify API is configured)
- **Food** — 3 iconic dishes with recipe links
- **Movies** — films from or about the country, with "where to watch" links
- **Country Facts** — capital, population, languages, currency, religion, fun fact
- **Passport** — sidebar tracks every country you've visited, with dates
- **User accounts** — username/password login or Google OAuth, persisted in SQLite

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Secrets

Create `.streamlit/secrets.toml` (not committed):

```toml
# Optional — enables live Spotify playlist search
SPOTIFY_CLIENT_ID = "your-spotify-client-id"
SPOTIFY_CLIENT_SECRET = "your-spotify-client-secret"

# Optional — enables Google OAuth login
GOOGLE_CLIENT_ID = "your-google-client-id"
GOOGLE_CLIENT_SECRET = "your-google-client-secret"
```

Both integrations are optional. The app works without them — Spotify falls back to a search link, and Google login is hidden if credentials aren't set.

## Tech stack

- [Streamlit](https://streamlit.io/) — UI
- SQLite — user accounts and visit history
- Spotify Web API — playlist search (optional)
- Google OAuth 2.0 — login (optional)
