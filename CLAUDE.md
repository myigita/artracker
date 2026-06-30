# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal tool to track an artist's (or several artists') work across multiple
platforms. The owner follows digital artists and wants one place to see when each
of them last posted, instead of checking six sites by hand.

**Current state: no code exists yet.** The repo contains only this spec
(originally `HANDOFF.md`). Treat the sections below as the plan to scaffold from,
not a description of existing code.

The work is scoped in two phases:

1. **MVP (start here):** a plain link manager. Add links, open them, and the app
   records when each link was last opened. No platform APIs, no accounts.
2. **Later:** layer live post-fetching on top, but *only* for the platforms that
   actually allow anonymous, browser-friendly reads (see the constraints table).

The owner explicitly chose to begin with the MVP and grow into live fetching.
Do not build platform integrations until the MVP is solid and the owner asks.

## How to collaborate (learning project)

This is a learning project — the owner is using it to build skill with this
stack, not just to get a working app. Default mode: **the owner writes the
implementation code; Claude guides and reviews.**

- Don't write full implementations (routes, models, components) unprompted.
  Explain the approach and relevant concepts, point at what needs to change and
  why, and review code the owner writes for bugs, idioms, and better patterns.
- Generating small non-learning boilerplate (initial scaffolding/config files)
  is reasonable — use judgment, and ask if unsure.
- If the owner explicitly asks for code to be written directly, do that for the
  request at hand, but don't default back to full-autonomy build-it-all mode
  afterward without being asked again.

## Stack (decided — Python + React)

- **Backend:** Python 3.12 + **FastAPI**, REST API, served by Uvicorn
- **DB:** SQLite via **SQLAlchemy** (single file `artracker.db`, schema created on startup)
- **Frontend:** **React + TypeScript + Vite** (single-page app)

This replaces an earlier Java/Spring Boot + Vue scaffold, which is **abandoned**.
Start fresh; do not port the old code.

### Why these choices (override deliberately, not by accident)

- **FastAPI over Django:** the app is a small JSON API, not a content site that
  needs Django's admin/ORM/templating. FastAPI is leaner here, has first-class
  typing via Pydantic, and auto-generates OpenAPI docs at `/docs`. *If the owner
  later wants a ready-made admin UI over the data, Django is the better pivot.*
- **React + TypeScript + Vite over Next.js:** this is a local, single-user tool with
  no SEO or server-rendering needs, so a plain Vite SPA is the honest fit and far
  simpler. *Next.js is the more job-relevant React framework, though — if the owner
  is building this partly to practice the most hireable setup, switching to Next.js
  is a reasonable, owner-gated upgrade.* Flag the trade-off; don't silently pick.
- **TypeScript, not plain JS:** it's now the expected form of React in the job
  market and catches a class of bugs for free. Keep it.

### CORS (cross-origin dev setup)

The React dev server (Vite, default `http://localhost:5173`) and the API
(`http://localhost:8000`) are different origins during development, so requests
are cross-origin. Two clean ways to handle it — pick one and document it:

- **Vite dev proxy (preferred):** proxy `/api` to `http://localhost:8000` in
  `vite.config.ts`. Frontend calls stay same-origin (`/api/...`), no CORS config
  needed, and it mirrors production.
- **FastAPI CORS middleware:** add `CORSMiddleware` allowing the Vite origin. Simple
  but only needed if you don't proxy.

For **production**, build the React app (`npm run build`) and serve the static
`dist/` from FastAPI (mount `StaticFiles`), collapsing back to one origin and one
process.

## Data model

> Revised from the original single-`Link`-table MVP spec: artists *and*
> platforms are now their own tables, so trackers reference both by FK instead
> of repeating free-text strings. `open_count` was dropped. Column names use
> `date_created` / `last_checked` (not `created_at` / `last_checked_at` from
> the original draft).

**`Artist`**

| field        | type          | notes                                |
|--------------|---------------|----------------------------------------|
| id           | int, PK       | autoincrement                        |
| name         | str, required | unique — prevents duplicate artists  |
| date_created | datetime      | set on insert                        |

**`Platform`**

| field        | type          | notes                                  |
|--------------|---------------|-------------------------------------------|
| id           | int, PK       | autoincrement                          |
| name         | str, required | unique — e.g. "Bluesky", "Pixiv"       |
| date_created | datetime      | set on insert                          |

**`Tracker`**

| field         | type           | notes                                              |
|---------------|----------------|-----------------------------------------------------|
| id            | int, PK        | autoincrement                                      |
| artist_id     | int, FK        | references `artists.id`, required                  |
| platform_id   | int, FK        | references `platforms.id`, required                |
| name          | str, required  | auto-built at creation as `"{artist.name} — {platform.name}"`, not client-supplied |
| url           | str, required  | the link to open/check                             |
| date_created  | datetime       | set on insert                                      |
| last_checked  | datetime, null | null until first check                             |

`Base` (the SQLAlchemy declarative base) is defined in `models.py`, not
`database.py` — `database.py` only owns `engine`/`SessionLocal` and imports
`Base` from `models.py` for `Base.metadata.create_all()`.

## API surface

| Method | Path                      | Purpose                                                       |
|--------|---------------------------|------------------------------------------------------------------|
| GET    | `/api/trackers`           | List all trackers (newest first)                              |
| POST   | `/api/trackers`           | Add a tracker `{artist_name, platform_name, url}` — looks up artist and platform by name or creates each if new; `name` is server-generated |
| POST   | `/api/trackers/{id}/check`| Record a check (stamp `last_checked`)                         |
| DELETE | `/api/trackers/{id}`      | Remove a tracker                                               |

Use Pydantic models for request/response. Return the updated tracker from the
`check` endpoint so the UI can refresh that row in place.

## Project layout (to scaffold)

```
artist-tracker/
├── backend/
│   ├── pyproject.toml          # or requirements.txt: fastapi, uvicorn[standard], sqlalchemy, pydantic
│   ├── app/
│   │   ├── main.py             # FastAPI app, router include, optional StaticFiles mount
│   │   ├── database.py         # engine, SessionLocal (imports Base from models.py)
│   │   ├── models.py           # Base, Artist, Platform, Tracker SQLAlchemy models
│   │   ├── schemas.py          # Pydantic request/response models
│   │   └── routes.py           # the four endpoints
│   └── artracker.db            # created at runtime (gitignore it)
└── frontend/
    ├── package.json            # vite, react, react-dom, typescript, @types/*
    ├── vite.config.ts          # /api proxy to :8000
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx             # list + add form + check/delete
        ├── api.ts              # typed fetch helpers
        └── components/         # TrackerCard, AddTrackerForm, etc.
```

## Commands (once scaffolded)

No code exists yet, so these aren't runnable today — set them up per the layout
above, matching this shape:

- Backend dev server: `uvicorn app.main:app --reload` (from `backend/`)
- Frontend dev server: `npm run dev` (from `frontend/`)
- Frontend build: `npm run build` (from `frontend/`)
- API docs: `http://localhost:8000/docs` (FastAPI auto-generated, use this to
  verify endpoints manually instead of guessing)

## Frontend behaviour (the MVP UX)

- An add form (artist name, platform name, url — all required) at the top.
- A list of cards, newest first, each showing tracker name, platform tag, url,
  and a relative "last checked" stamp (e.g. "3h ago", "never").
- **Signature detail to keep:** the last-checked stamp's colour ages from a warm
  accent (checked today) to muted grey (stale), so neglected trackers surface
  visually.
- Clicking **Open** opens the url in a new tab *and* POSTs to
  `/api/trackers/{id}/check`, then updates that card in place. Opening must
  still work even if the stamp POST fails (fire-and-forget).
- A delete (✕) per card.
- Empty state: a short prompt to add the first tracker.
- Quality floor: responsive to mobile, visible keyboard focus, respects
  `prefers-reduced-motion`.

## Platform access constraints (researched June 2026 — reuse, don't re-derive)

This is the hard-won part. When live fetching is eventually built, only two sources
can be polled anonymously from a browser. The rest need credentials a fan-built
tracker can't obtain, so they stay as saved links with a manual "last opened" stamp.

| Platform      | Live fetch? | Notes |
|---------------|-------------|-------|
| Bluesky       | Yes         | `https://public.api.bsky.app` — public AppView, no auth, CORS-friendly. Resolve handle → DID via `com.atproto.identity.resolveHandle`, then `app.bsky.feed.getAuthorFeed`. |
| Danbooru      | Yes         | `https://danbooru.donmai.us/posts.json?tags=<artist_tag>` — anonymous + CORS, capped at 2 tags/search (fine for one artist). Caveat: community-tagged, so there's lag and coverage isn't guaranteed. |
| Gelbooru      | Conditional | Requires a free account + API key (user_id + api_key) since 2025. Only wire in if the owner provides a key. |
| Pixiv         | No          | No official public API; reverse-engineered endpoints need a logged-in account's session creds. Saved link only. |
| Twitter/X     | No          | Pay-per-use only since Feb 2026 (~$0.005/read), needs a paid dev account + a server to hold the key. Saved link unless the owner plugs in their own key. |
| SubscribeStar | No          | OAuth2/GraphQL API is creator-side only (subscriber/payment scopes); no endpoint for a subscriber to read a creator's posts. Saved link only. |
| Discord       | No          | Reading messages needs a bot token + admin invite per server. Saved link only. |

When you do build live fetching:
- Bluesky and Danbooru are both CORS-OK, so they can be called from the React app
  directly, or proxied through FastAPI to centralise caching/rate-limiting. Backend
  proxying is the cleaner long-term choice once there's more than one source — and
  with FastAPI's async + httpx it's straightforward.
- Persist a per-link "last seen post id / timestamp" so you can show a *"new since
  you last opened"* badge — that's the real payoff over the manual MVP.

## Suggested next steps, in order

1. Scaffold the backend; get the four endpoints working against SQLite; verify at
   `/docs`.
2. Scaffold the Vite + React + TS frontend; wire the `/api` proxy; build the list +
   add + open + delete flow.
3. Smoke-test end to end; commit a known-good MVP.
4. Add the production path: `npm run build` + FastAPI `StaticFiles` serving `dist/`,
   so the whole thing runs as one process.
5. (Owner-gated) Add live fetching for Bluesky first — cleanest API, immediate
   value. Danbooru second.
6. (Owner-gated) Add the "new since last opened" badge once a live source is in.

## Things to confirm with the owner before doing them

- Switching the frontend to **Next.js** (more job-relevant, but adds SSR this app
  doesn't need) — currently a plain Vite SPA by choice.
- Switching the backend to **Django** (gains an admin UI, heavier) — currently
  FastAPI by choice.
- Moving the DB off SQLite, or adding Alembic migrations.
- Building any platform integration beyond Bluesky/Danbooru.
- Multi-user / auth — the MVP assumes a single local user, no login.
