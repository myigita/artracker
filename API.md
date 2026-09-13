# Artracker API

Reference for driving Artracker from outside the web UI — scripts, agents, or a
second instance. Everything the UI does is available here; there is no private
endpoint.

- **Base URL, local dev:** `http://localhost:8000`
- **27 endpoints**, all listed below
- **Machine-readable spec:** `GET /openapi.json` · interactive console at `/docs`
  — **both are disabled when `ARTRACKER_ENV=production`**, so on the deployed
  instance they 404. Use this document there.

## Before anything else: two things that will bite you

**1. There is no authentication.** Not a token, not a header, nothing. Anything
that can reach the port has full read/write/delete over every row. On the VPS the
only thing in front is the Cosmos auth gate, so an external agent cannot reach the
API without getting through Cosmos first. In practice that means either running the
agent somewhere it can reach the container directly, or having it produce a backup
file (see below) that you import by hand.

**2. Trailing slashes are load-bearing.** Collection paths end in `/`; paths with
an id do not.

```
GET  /api/trackers/              correct
GET  /api/trackers               wrong
POST /api/trackers/{id}/check    correct — no trailing slash
GET  /api/backup/export          correct — no trailing slash
```

What a wrong slash does **depends on the deployment**, which is the part that
catches people out:

| Situation | Result |
|-----------|--------|
| Dev, backend alone with no built frontend | **307** redirect, silently followed |
| Production, or any run after `npm run build` | **404** |

In production the app mounts the built React bundle at `/`, and that mount
matches the unmatched path before FastAPI's `redirect_slashes` fallback gets a
chance — so the forgiving redirect you saw in dev is simply gone. Code written
against a dev server can pass locally and 404 in production. Write the slash.

---

## Bulk ingest: the endpoint an agent should actually use

`POST /api/backup/import?mode=merge` is the only endpoint that creates rows
**across all four tables in one request**, resolving references in dependency
order. It exists for backup restore, but it is by far the best ingest path:

- **No pre-flight ordering.** Categories, platforms and subjects are created as
  needed. The one-at-a-time endpoints refuse to auto-create (see below), so
  without this you'd need four round trips per tracker plus 409 handling.
- **Safe to re-run.** `merge` skips anything already present, so an agent that
  runs twice — or is interrupted and retried — adds nothing the second time.
- **All-or-nothing.** If any row references something that doesn't exist, the
  whole request 400s and the database is left untouched.

### Request

```json
{
  "version": 1,
  "categories": [{ "name": "Artist" }],
  "platforms": [{ "name": "Bluesky" }, { "name": "Danbooru" }],
  "subjects": [
    { "name": "Kentaro Miura", "category_name": "Artist" },
    { "name": "Yoshitoshi ABe", "category_name": "Artist" }
  ],
  "trackers": [
    {
      "name": "Kentaro Miura on Bluesky",
      "subject_name": "Kentaro Miura",
      "platform_name": "Bluesky",
      "url": "https://bsky.app/profile/miura.example",
      "description": "found by agent"
    },
    {
      "name": "abe tag on Danbooru",
      "subject_name": "Yoshitoshi ABe",
      "platform_name": "Danbooru",
      "url": "https://danbooru.donmai.us/posts?tags=abe_yoshitoshi"
    }
  ]
}
```

### Response

```json
{
  "mode": "merge",
  "categories_added": 1,
  "platforms_added": 2,
  "subjects_added": 2,
  "trackers_added": 2,
  "skipped": 0,
  "deleted": 0
}
```

Running the identical request again returns all zeros with `"skipped": 7`.

### Rules

- **Rows reference each other by name, never by id.** Ids are not part of the
  format at all — they aren't exported and are ignored if sent.
- `version` must be `1`. Anything else 400s.
- Every list is optional; an empty document is a valid no-op.
- **Identity for skipping (merge only):** the unique `name` for categories,
  platforms and subjects; the whole **`(subject_name, platform_name, url)`**
  triple for trackers. Not the URL alone — two subjects can legitimately point at
  the same page, and treating those as one row loses one of them.
- **`replace` skips nothing.** The tables are empty by that point, so every row
  in the file is inserted, including rows that are identical to each other.
- `date_created` and `last_checked` are optional. Omit them and `date_created`
  defaults to now, `last_checked` to null ("never checked").
- **`?mode=replace` deletes all four tables first.** Only use it for restoring a
  real backup. `merge` is the default, so an unqualified POST cannot wipe data.

### Getting data back out

`GET /api/backup/export` returns the same shape, plus `exported_at`. This is the
whole database in one request — useful for an agent that needs to know what's
already tracked before deciding what to add.

---

## Endpoint reference

### Trackers

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/trackers/` | All trackers, newest first |
| `GET` | `/api/trackers/{id}` | 404 if missing |
| `POST` | `/api/trackers/` | **201.** 400 if the subject or platform doesn't exist |
| `PATCH` | `/api/trackers/{id}` | Partial update · 404 if missing |
| `GET` | `/api/trackers/{id}/updates` | Detected updates, newest first · 404 if missing |
| `POST` | `/api/trackers/{id}/check` | Stamps `last_checked` to now, returns the tracker |
| `DELETE` | `/api/trackers/{id}` | **200**, returns the deleted row |

**`POST` body** — `subject_name` and `platform_name` are required; `url` is not:

```json
{
  "subject_name": "Kentaro Miura",
  "platform_name": "Bluesky",
  "url": "https://bsky.app/profile/miura.example",
  "name": "optional, defaults to \"Subject (Platform)\"",
  "description": "optional",
  "rules": [
    { "field": "sender", "operator": "contains", "value": "peargor" }
  ]
}
```

> **A tracker needs a URL or at least one match rule**, and 400s with neither.
> URL only is a manual bookmark. Rules only is an artist watched purely through
> notification mail, with no page to open. Both is the useful case.
>
> Omitted `rules` and `[]` both mean no rules. A platform domain is shared by
> every artist there, so it is never installed as an automatic tracker rule.

> **No auto-create.** If the subject or platform doesn't already exist this
> returns **400**, it does not create them. Create them first (treating 409 as
> success), or use the bulk import above.

**`PATCH` body** — every field optional; only the keys you send are changed, so
omitting a key is different from sending `null`:

```json
{ "name": "…", "url": "…", "description": null, "rules": [], "last_checked": null }
```

`description` and `last_checked` accept `null` (clearing a description, undoing a
check). `name` does not — an explicit `null` there returns 400.

`url` and `rules` may each be emptied, but **not both**: whichever you clear, the
other has to remain, or the request 400s. Rules are replaced wholesale — send the
full list you want, not a delta.

**Response shape:**

```json
{
  "id": 1,
  "name": "Kentaro Miura - Bluesky",
  "subject_name": "Kentaro Miura",
  "subject_category": "Artist",
  "platform_name": "Bluesky",
  "url": "https://bsky.app/profile/miura.example",
  "description": null,
  "rules": [
    { "id": 4, "field": "sender", "operator": "contains", "value": "bsky.app" }
  ],
  "date_created": "2026-08-14T17:59:00.799257+00:00",
  "last_checked": null,
  "unread_count": 0
}
```

`subject_category` is derived from the tracker's subject — it is read-only here,
and changes when you recategorize the subject.

`unread_count` is updates detected since `last_checked`, computed rather than
stored. `POST /{id}/check` therefore drops it to zero, and PATCHing `last_checked`
back to an earlier value (or `null`) brings it back.

### Match rules

What makes a message land on a tracker. **Every rule on a tracker must hold** —
they are ANDed, which is what makes the negative operators useful ("from this
sender, but not the weekly digest").

| Key | Values |
|-----|--------|
| `field` | `sender` · `subject` |
| `operator` | `contains` · `not_contains` · `equals` · `not_equals` |
| `value` | 1–500 characters |

Matching is case-insensitive on both sides. `sender` is the bare address with the
display name stripped, so `Pear哥 <peargor@creator.patreon.com>` matches a rule
against `peargor@creator.patreon.com` but not one against `Pear哥`.

Every non-empty rule set needs at least one positive `contains` or `equals` rule.
`not_contains` and `not_equals` only narrow that positive match; alone they would
accept nearly every unrelated message in the mailbox.

**A tracker with no rules never matches anything**, deliberately — otherwise every
rule-less tracker would claim every message. One message *can* land on several
trackers, and records an update on each.

The message body is not a field. Headers are already in hand after a fetch;
bodies mean parsing multipart HTML, and that is where false positives live.

### Updates

`GET /api/trackers/{id}/updates` returns what the poller has recorded:

```json
[
  {
    "id": 12,
    "tracker_id": 1,
    "summary": "August Character Poll",
    "detected_at": "2026-08-30T04:42:00+00:00"
  }
]
```

`summary` is the notification's subject line. Updates are deleted with their
tracker.

### Subjects

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/subjects/` | Alphabetical |
| `POST` | `/api/subjects/` | **201** · **409** if the name exists · 400 if `category_name` is unknown |
| `PATCH` | `/api/subjects/{id}` | Sets the category only · 404 if missing |
| `DELETE` | `/api/subjects/{id}` | **204** · **409** if any tracker still references it |

```json
POST  { "name": "Kentaro Miura", "category_name": "Artist" }
PATCH { "category_name": "Artist" }     // null clears it; omit to leave alone
```

`PATCH` is deliberately narrow — it cannot rename a subject.

### Platforms and Categories

Identical shape to each other:

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/platforms/` · `/api/categories/` | Alphabetical |
| `POST` | `/api/platforms/` · `/api/categories/` | **201** · **409** if the name exists |
| `DELETE` | `/api/platforms/{id}` · `/api/categories/{id}` | **204** · **409** if still referenced |

Body is `{ "name": "…" }`. Deleting a platform 409s while any **tracker** uses it;
deleting a category 409s while any **subject** uses it.

Platforms take one extra optional field:

```json
POST /api/platforms/  { "name": "Patreon - Mail", "mail_domain": "creator.patreon.com" }
```

`mail_domain` tells the UI that the platform supports notification mail and gives
it a useful hint. It is not installed as a rule because the same domain is shared
by every artist. It is unique across platforms, and 409s if another claims it.

Platform responses also carry **`is_preset`**. The app seeds a small set of known
platforms at startup and **refuses to delete them (409)** — deleting would appear
to work and then have the row reappear on the next restart.

### Notification mail

How updates are actually detected. The app reads a gathering mailbox over IMAP and
records an update on every tracker whose rules the message satisfies.

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/mail/poll` | Read the mailbox once, now · **503** unconfigured · **502** unreachable |
| `GET` | `/api/mail/unmatched` | Mail that matched no tracker, newest first |
| `DELETE` | `/api/mail/unmatched/{id}` | **204** · dismiss one · 404 if missing |
| `GET` | `/api/mail/account` | Mailbox settings — **never the password** |
| `PUT` | `/api/mail/account` | Save them · 400 if no password was ever set |
| `DELETE` | `/api/mail/account` | **204** · forget them · 404 if none stored |
| `GET` | `/api/mail/schedule` | The background poller's settings |
| `PUT` | `/api/mail/schedule` | Change them |

**Poll response:**

```json
{ "fetched": 3, "recorded": 2, "duplicates": 0, "unmatched": 1 }
```

Safe to call as often as you like: each recorded update is keyed by the message's
`Message-ID` scoped to its tracker, so re-reading the same mail records nothing new.
The poller also saves the mailbox's IMAP UID cursor and fetches headers with
`BODY.PEEK`, so opening a message in Gmail neither hides it from Artracker nor has
its read state changed by Artracker. The cursor advances only with the database
transaction that records the batch.

**Unmatched mail is a diagnostic, not a queue.** Sender addresses and subject
formats change without notice, and a poller that silently dropped what it couldn't
match would look exactly like an artist who stopped posting. Each row carries the
`reason` it was rejected.

#### Mailbox credentials

```json
GET   → { "host": "imap.gmail.com", "port": 993, "username": "gather@example.com",
          "mailbox": "INBOX", "has_password": true, "source": "database" }
PUT   ← { "host": "…", "port": 993, "username": "…", "password": "…", "mailbox": "INBOX" }
```

- **The password is never returned by any endpoint**, and is not in the backup
  document. `has_password` is all you get. Every endpoint here is unauthenticated,
  so a password on a response model is a password served to anyone who can reach
  the app.
- **Omit `password` on `PUT` to keep a database-stored password.** Environment
  credentials cannot be copied through the API, so the first save from
  `source: "environment"` must include the app password again. An empty string is
  rejected rather than treated as a clear.
- `source` is `database`, `environment` or `unset`. A stored account wins over the
  `ARTRACKER_MAIL_*` environment variables; those remain as a fallback, so
  `DELETE` degrades to them rather than switching the feature off.

#### Schedule

```json
GET → { "enabled": false, "interval_minutes": 15, "last_run_at": null,
        "last_result": null, "next_run_at": null }
PUT ← { "enabled": true, "interval_minutes": 30 }
```

- **`interval_minutes` is 5–1440.** Anything outside that 422s. Five is the floor
  because IMAP servers rate-limit and notification mail arrives in bursts anyway.
- Off by default. The poller runs inside the app process, so there is nothing to
  configure on the host.
- `last_result` is a one-line summary of the last pass, or the error it failed
  with — a background poller has no request to watch fail, so it is the only
  feedback there is.
- A schedule that has never run is due immediately. Afterwards `next_run_at` is
  computed from `last_run_at`. Manual checks update the same last/next-run state.

### Backup

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/backup/export` | The whole database as one document |
| `POST` | `/api/backup/import?mode=merge\|replace` | Defaults to `merge` |

The document carries match rules and platform mail domains, since both are
configuration. It does **not** carry detected updates, unmatched mail, or the
mailbox password — the first two are re-derivable signals rather than settings,
and the third has no business in a file you download and pass around.
Replace imports also restore any missing built-in platforms, so a version-1 backup
from before Patreon Mail existed cannot leave the preset missing.

---

## Status codes

| Code | Means |
|------|-------|
| `400` | A referenced name doesn't exist, or a null was sent for a non-nullable field |
| `404` | No row with that id |
| `409` | Name already taken, or the row is still referenced by something else |
| `422` | Body failed validation — missing field, wrong type, blank or oversized string |
| `502` | The mailbox could not be reached — the app is fine, the mail server isn't |
| `503` | No mailbox is configured yet |

**409 is usually success in disguise.** When an agent is ensuring a subject
exists, "it already exists" is the desired end state, not an error. The web UI
treats it that way; scripts should too.

## Field limits

Enforced by Pydantic, not the database — SQLite ignores `VARCHAR` lengths, so
these are the only real bound.

| Field | Limit |
|-------|-------|
| `name` (all tables) | 1–255 characters |
| `url` | 1–2000 characters |
| `description` | ≤ 1000 characters |
| match rule `value` | 1–500 characters, ≤ 25 rules per tracker |
| `interval_minutes` | 5–1440 |

Strings are stripped of surrounding whitespace, so `"  Denji  "` is stored as
`"Denji"` and `"   "` is rejected as blank with a 422.

## Datetimes

Sent and received as ISO 8601 **marked UTC**: `2026-08-14T17:59:00.799257+00:00`.

Inbound values with any offset are converted to UTC, so `12:00+03:00` is stored as
`09:00Z` — the same instant. Naive strings with no offset are taken as UTC as-is.

The marker matters on the way out: without it, `new Date("2026-07-15T17:37:13")`
in a browser reads the value as *local* time and every timestamp silently skews by
the client's offset.
