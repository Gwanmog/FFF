# Project: Funky Fresh Friday - Full Immersion Date Night App

## Role
You are an expert Python/Streamlit developer. Build a multicultural discovery app called "Funky Fresh Friday" that persists user progress across sessions.

## Tech Stack
- **Frontend/UI:** Streamlit
- **Database:** SQLite (using standard `sqlite3` or `SQLAlchemy`) for state persistence.
- **Data Source:** Ensure a 2026-accurate master list of all official sovereign countries.

## Core Features & Logic

### 1. Persistent User Accounts
- Implement a simple login screen (Username/Password). 
- Store users in a `users` table in SQLite.
- **State Persistence:** On login, retrieve the user's `past_countries` from the database so they never lose their "Passport" history.

### 2. The "Funky Fresh" Randomizer
- Fetch the full list of official countries (as of 2026).
- **Exclusion Logic:** Filter out any countries found in the user's personal history in the DB.
- Select one random country from the remaining pool.
- **Database Entry:** Immediately save the selection to a `user_history` table linked to the user ID. 

### 3. Cultural Immersion Modules
Upon selection, display the following in high-energy, card-based UI sections:

- **Music (Spotify Playlist):** - Generate a curated list or direct link for a 50-song Spotify playlist.
    - Content must be a mix of **traditional/folk music** and **modern popular artists** from that specific country.
- **Food (Iconic Recipes):** - Display 3 dishes that are considered **famous**, the **"national dish"**, or are **generally iconic** to that culture.
    - Look up and provide links to recipes for each. 
    - **Constraint:** Links must open in a new tab (`target="_blank"`) so the user doesn't lose their Streamlit session.
- **Movies (Cinematic Connection):** - Suggest up to 10 movies that were **filmed in that country**, **produced by that country’s film industry**, or have a **deep relation to that country and its culture**.
    - Include "Where to Watch" info (streaming platform links or search results).

### 4. UI/UX & Visuals
- **Passport History:** Use the sidebar to show a chronological list of past visited countries.
- **Celebration:** Trigger `st.balloons()` when a new country is generated.
- **Styling:** Use a vibrant, "funky" color palette. 
- **Reset:** Include a "Clear My World History" button to wipe the user's database records if they want to start over.