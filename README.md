# 🌍 Funky Fresh Friday

A cultural immersion app for date nights. Spin the globe and get dropped into a random country — with music, food recipes, and movies to match.

## What it does

- **Spin the Globe** — randomly picks a country you haven't visited yet
- **Music** — artists to know + Spotify playlist links (live search if Spotify API is configured)
- **Food** — 3 iconic dishes with recipe links
- **Movies** — films from or about the country, with "where to watch" links
- **Country Facts** — capital, population, languages, currency, religion, fun fact
- **Passport** — sidebar tracks every country you've visited, with dates
- **User accounts** — username/password login or Google OAuth

## Run it locally

```bash
pip install -r requirements.txt
python check_setup.py          # reports what's configured and what works
streamlit run app.py
```

On Windows, run it through the project venv so you get the right interpreter —
a bare `streamlit` on PATH may resolve to a different Python that is missing
`requests-oauthlib`:

```
.venv\Scripts\python.exe -m streamlit run app.py
```

## Configuration

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in
what you want. **Every key is optional** — with none of them set the app still
runs with curated country facts, username/password login, and Spotify search links.

| Key | Enables | Without it |
| --- | --- | --- |
| `RESTCOUNTRIES_API_KEY` | Live capital, population, area, flag, languages, currency | Card shows curated facts only, and says why |
| `SPOTIFY_CLIENT_ID` / `_SECRET` | Real playlist search with cover art | Plain Spotify search link |
| `GOOGLE_CLIENT_ID` / `_SECRET` | "Continue with Google" | Button is hidden |
| `APP_URL` | Google redirect target | Defaults to `http://localhost:8501` |
| `DATABASE_URL` | Postgres storage | Local SQLite file |

`check_setup.py` verifies all of these against the live services:

```bash
python check_setup.py           # quick check
python check_setup.py --facts   # also probe all 197 country names
```

## Deploying

See **[DEPLOY.md](DEPLOY.md)** for the full walkthrough — free Postgres, API
keys, Streamlit Cloud setup, Google OAuth, and troubleshooting.

The two things that differ from local, and will bite you if skipped:

1. **The filesystem is ephemeral.** A SQLite file is wiped on every reboot,
   taking all accounts and passport history with it. Set `DATABASE_URL`.
2. **The URL changes.** Set `APP_URL` and register it in Google Cloud, or Google
   login fails with `redirect_uri_mismatch`.

## Tech stack

- [Streamlit](https://streamlit.io/) — UI
- SQLite (local) / Postgres (deployed) — user accounts and visit history
- [RestCountries v5](https://restcountries.com/) — live country data (optional)
- Spotify Web API — playlist search (optional)
- Google OAuth 2.0 — login (optional)

## Notes

- Passwords are stored as salted PBKDF2-SHA256. Accounts created before that
  change hold a bare SHA-256 digest and are upgraded automatically on next login.
- RestCountries v3.1 was deprecated and now returns HTTP 200 with an error body,
  which is why `country_facts.py` validates the response body rather than
  trusting the status code.
