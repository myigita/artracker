# Artracker

Track when an artist last posted, across all the places they post.

If you follow digital artists across six different sites, checking each one by
hand gets old fast. Artracker is one page that lists every artist–platform pair
you care about. Click **Open**, it opens the link and stamps the time — so the
list always tells you where you're behind.

It's a link manager with a memory, not a scraper. Most art platforms don't
allow anonymous reads (see [CLAUDE.md](CLAUDE.md) for the per-platform
research), so the timestamps come from your own clicks.

## What's in it

- **Trackers** — a subject + platform + URL, with a relative "last checked"
  stamp and an undo if you click Open by mistake
- **Subjects, platforms, categories** — managed in their own tabs, with delete
  guards so you can't orphan a tracker
- **Backup** — export everything to JSON, import it back in merge or replace
  mode. References are by name, so a backup restores into any database

## Stack

Python 3.12 · FastAPI · SQLAlchemy · SQLite — React 19 · TypeScript · Vite ·
Tailwind v4. One SQLite file, no accounts, single user.

## Running it

First time:

```bash
python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt && npm --prefix frontend install
```

Then:

```bash
./run.sh
```

That starts both dev servers and stops both on Ctrl-C. Open
**http://localhost:5173** — not `:8000`. Vite proxies `/api` to the backend, so
the app stays same-origin and needs no CORS config.

Tests:

```bash
backend/.venv/bin/pytest
```

## Production

One container serves the API and the built frontend together:

```bash
docker compose up --build
```

The named volume `artracker-data` holds the database. Without it, every rebuild
silently wipes your trackers.

**The app has no authentication of its own** — every endpoint is open to
whatever can reach the container. The published port is bound to `127.0.0.1` on
purpose; put it behind a reverse proxy with an auth gate before exposing it.

## API

[API.md](API.md) documents all 18 endpoints. Interactive docs are at
`/docs` in development, and disabled when `ARTRACKER_ENV=production`.

## Branches

- **`main`** — stable. What's been tested and works.
- **`beta`** — integration. Feature branches merge here first; once it's
  verified, `beta` promotes to `main`.
- **`artisanal`** — a frozen snapshot of the hand-written original, kept as the
  starting point for a separate from-scratch rewrite.

## License

MIT — see [LICENSE](LICENSE).
