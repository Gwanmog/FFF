# Deploying Funky Fresh Friday

Getting the app live on Streamlit Community Cloud, free, with working accounts,
Google login, and live country data.

Two things differ from running locally, and both will bite you if skipped:

1. **The filesystem is ephemeral.** A SQLite file is wiped on every reboot and
   redeploy, taking all accounts and passport history with it. You need a hosted
   Postgres.
2. **The URL changes.** Google login fails with `redirect_uri_mismatch` unless
   the deployed URL is registered as an Authorized redirect URI.

Budget about 20 minutes. Everything below is free tier, no credit card.

---

## 1. Push the code

```bash
cd C:\Users\Alexander\PycharmProjects\FFF
git add -A
git commit -m "Deploy config"
git push
```

`.streamlit/secrets.toml` is gitignored, so your real keys stay out of the public
repo. Only `.streamlit/secrets.toml.example` is committed.

## 2. Create a free Postgres database

**Use [Neon](https://neon.tech), not Supabase.** Supabase's free tier pauses a
project after about 7 days of inactivity and needs a *manual* unpause from the
dashboard — for an app used once a week, that's a coin flip on whether Friday
works. Neon auto-suspends when idle but resumes automatically on the next
connection.

1. Sign up and create a project.
2. Copy the connection string — it looks like
   `postgresql://user:password@host.neon.tech/dbname?sslmode=require`.
3. Keep it handy for step 5.

Free tiers change; check the current terms when you sign up.

<details>
<summary>Using Supabase instead</summary>

Project Settings → Database → Connection string → URI. Use the **Transaction
pooler** host (port `6543`), not the direct connection. Be aware of the pausing
behaviour above.
</details>

## 3. Get a country-facts API key

RestCountries v3.1 was shut down, which is what broke the live facts. v5 needs a
free key:

1. Sign up at [restcountries.com/sign-up](https://restcountries.com/sign-up) —
   no credit card.
2. Copy the key from the dashboard.

This one is genuinely optional. Without it the app still runs and shows curated
facts (religion, national sport, industries, fun fact) plus a note explaining
that capital/population/flag are unavailable.

## 4. Create the Streamlit app

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → repository `Gwanmog/FFF`, branch `master`, main file `app.py`.
3. Open **Advanced settings**:
   - Set **Python version 3.12**. `psycopg2-binary` does not publish wheels for
     every newer version, and the build will fail without this.
   - Choose a **custom subdomain**, e.g. `funky-fresh-friday`. This fixes your
     URL up front, which you need for the next step.

## 5. Add the secrets

Still in Advanced settings, paste into the **Secrets** box — same TOML format as
the local file:

```toml
RESTCOUNTRIES_API_KEY = "your-key-from-step-3"

SPOTIFY_CLIENT_ID = "reuse-your-existing-value"
SPOTIFY_CLIENT_SECRET = "reuse-your-existing-value"

GOOGLE_CLIENT_ID = "reuse-your-existing-value"
GOOGLE_CLIENT_SECRET = "reuse-your-existing-value"

APP_URL = "https://your-subdomain.streamlit.app"
DATABASE_URL = "postgresql://...from-step-2..."
```

Then click **Deploy**. First build takes a few minutes.

You can edit secrets later from the app's ⋮ menu → **Settings → Secrets**. Saving
reboots the app.

## 6. Authorize the URL with Google

Otherwise "Continue with Google" fails.

1. [console.cloud.google.com](https://console.cloud.google.com) → **APIs &
   Services → Credentials** → your OAuth 2.0 Client ID.
2. Under **Authorized redirect URIs**, add your deployed URL:
   `https://your-subdomain.streamlit.app`
   It must match `APP_URL` character for character — no trailing slash, no
   `http://`.
3. Check the **OAuth consent screen**. If it is still in *Testing*, only listed
   test users can log in. Add whoever will use the app under **Test users**, or
   publish the app.

Changes can take a few minutes to take effect on Google's side.

## 7. Verify

Open the URL and:

- Sign up for an account, log out, log back in — confirms Postgres is wired up.
- Spin the globe. The Quick Facts card should show a flag, capital and
  population, with **no** warning caption underneath.
- Reboot the app from the Streamlit dashboard, then log in again. If your account
  survives, persistence is working. If it doesn't, `DATABASE_URL` isn't being
  read and you're still on ephemeral SQLite.

To check everything from your machine at any point:

```bash
python check_setup.py           # what's configured, what works
python check_setup.py --facts   # probe all 197 country names
```

---

## Secrets reference

Every key is optional. With none set, the app still runs.

| Key | Enables | Without it |
| --- | --- | --- |
| `RESTCOUNTRIES_API_KEY` | Live capital, population, area, flag, languages, currency | Curated facts only, with a visible note |
| `SPOTIFY_CLIENT_ID` / `_SECRET` | Playlist search with cover art | Plain Spotify search link |
| `GOOGLE_CLIENT_ID` / `_SECRET` | "Continue with Google" | Button hidden, username/password still works |
| `APP_URL` | Google redirect target | Defaults to `http://localhost:8501` |
| `DATABASE_URL` | Postgres storage | Local SQLite file — **wiped on every Cloud reboot** |

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Build fails on `psycopg2` | Python version not pinned to 3.12 in Advanced settings |
| Accounts vanish after a reboot | `DATABASE_URL` not set or not being read — still on SQLite |
| `redirect_uri_mismatch` on Google login | `APP_URL` and the Google Authorized redirect URI don't match exactly |
| Google login works for you, nobody else | OAuth consent screen still in *Testing* — add test users or publish |
| ⚠️ caption under the facts card | Read it — it names the exact failure (no key, bad key, rate limit, no match) |
| A country shows no flag or capital | Name mismatch upstream. Run `python check_setup.py --facts`, add the country to `NAME_ALIASES` in `country_facts.py` |
| `ModuleNotFoundError: requests_oauthlib` locally | Wrong interpreter. Use `.venv\Scripts\python.exe -m streamlit run app.py` |

## Notes

- **Existing local data does not migrate.** The 2 accounts and 28 visited
  countries in your local `funky_fresh.db` stay local; the deployed app starts
  empty.
- **The repo is public.** Any credential that has ever been pasted somewhere
  shared is worth rotating.
