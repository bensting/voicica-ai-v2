# Backend

FastAPI app implementing the TTS vertical slice (see the repo root [README](../README.md) and [`docs/`](../docs/README.md) for the architecture this follows — this file is just "how to run it").

## Setup

```bash
py -m venv .venv                       # or: python -m venv .venv
.venv\Scripts\activate                  # Windows; source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

copy .env.example .env                  # then fill in the values — see .env.example's comments
```

You'll need, at minimum, to get from outside this repo:

- A **Postgres** database. Local dev, quickest path: `docker run -d --name voicica-db -e POSTGRES_USER=voicica -e POSTGRES_PASSWORD=voicica -e POSTGRES_DB=voicica -p 5432:5432 postgres:16` (matches `.env.example`'s default `DATABASE_URL`).
- A **Firebase** project's service account key ([ADR 0008](../docs/decisions/0008-auth-provider.md)) — download it from the Firebase console and save it as `../secrets/firebase-adminsdk.json` (see [`../secrets/README.md`](../secrets/README.md) — that whole folder is gitignored except its own README, on purpose, so real credentials have one findable, non-git home instead of scattering across Downloads). `.env`'s `FIREBASE_CREDENTIALS_PATH` already points there.
- A **Fish Audio** API key from <https://fish.audio/app/api-keys/>.
- A **Cloudflare R2** bucket + access key ([ADR 0004](../docs/decisions/0004-asset-mirroring-r2-retention.md)).
- An **Azure Speech** resource's key + region (Azure Portal → your Speech resource → "Keys and Endpoint" — the region matters, the API endpoint is region-specific).
- A **Google Cloud Text-to-Speech** API key (Cloud Console → APIs & Services → Credentials, with that API enabled — a plain API key is enough, no service account needed).

## Run migrations

```bash
alembic upgrade head
```

This creates the schema ([`docs/data-model.md`](../docs/data-model.md)) and seeds `app_settings`' placeholder values ([ADR 0012](../docs/decisions/0012-app-settings-table.md)).

Then sync the voice catalog (Azure + Google — [ADR 0007](../docs/decisions/0007-scheduled-tasks-module.md)) before anything can use a non-default voice:

```bash
python -m app.scheduled.sync_catalog
```

Pulls each configured provider's real voice list into `voice_catalog`. Safe to re-run any time (wholesale overwrite per provider, not a diff). No scheduler runs this automatically yet — that's still ADR 0007's open item — so re-run it by hand when a provider's catalog might have changed.

## Run the app

```bash
uvicorn app.main:app --reload --port 8000
```

Or in PyCharm: the **"Backend"** run configuration (`.run/Backend.run.xml`, checked into the repo) runs the same command — pick it from the run-configuration dropdown. It uses the module's configured Python interpreter rather than a hardcoded path, so first set the project interpreter to `backend/.venv` (Settings → Project → Python Interpreter → Add → Existing → `backend/.venv/Scripts/python.exe`) if you haven't already.

Then `GET http://localhost:8000/health` should return `{"status": "ok"}`, and `http://localhost:8000/docs` has the interactive OpenAPI UI — every route needs a Firebase ID token as a bearer token except `/health`.

## What's implemented (this slice)

- `POST /generate/tts` → `GET /jobs/{id}` / `GET /jobs` — submit and read back a TTS job, credits held/settled/released around it ([ADR 0002](../docs/decisions/0002-unified-async-job-model.md), [ADR 0003](../docs/decisions/0003-credit-ledger-hold-then-settle.md)). **Exactly one of `voice_id`/`voice_model_id` is required** — which provider gets called is decided entirely by whichever voice was resolved (a `voice_catalog` row, or a user's own `voice_models` row, ADR 0009), not a separate provider field (architecture.md §3c, `services/jobs.py submit_tts`). Fish Audio isn't a general fallback, it's reserved for a user's own cloned voices — an earlier version of this defaulted to Fish Audio's own generic voice when no `voice_id` was given, which had nothing to do with what the picker actually offers; corrected once that was pointed out. Optional `speed`/`volume`/`pitch` (0.5-2.0x / 1-100 / 1-100, one scale for every provider) get converted to each adapter's own units — exact formulas ported from the prior project's verified-in-production conversions, not re-derived; Fish Audio has no pitch control and ignores that one; some Google voices (Chirp3 HD) reject `pitch` outright, so `providers/google.py` retries once without it on that specific error rather than failing the whole request. Fish Audio's TTS model (`s2.1-pro`, their current recommended model — the prior project's `speech-1.5`/`speech-1.6` were deprecated by Fish Audio on 2026-02-28, so weren't carried forward) is an `app_settings` value (`fish_tts_model`, [ADR 0012](../docs/decisions/0012-app-settings-table.md)), not a hardcoded constant — read fresh per-request in `services/jobs.py submit_tts`, same as `tts_credits_per_10_chars`, so bumping it to whatever Fish recommends next is `PATCH /admin/settings/fish_tts_model`, no deploy. Verified: reading the default, writing a different value and seeing a fresh read reflect it immediately (no restart, no caching), and a real Fish Audio call succeeding with that value in the header — then restored to `s2.1-pro`.
- `GET /catalog/voices?provider=&locale=&language=` / `GET /catalog/languages?provider=` — the synced voice picker data. Azure + Google's real catalogs (`app/scheduled/sync_catalog.py`), every language either supports (82 distinct base languages, 158 locale variants) — no target-market restriction; the picker keeps its payload small by always fetching one *language*'s voices at a time (`language=es` matches every `es-*` locale across every provider), not by narrowing which languages exist or by picking one exact locale (`services/voice_catalog.py`'s module docstring explains all three corrections here — availability, exact-locale-vs-base-language, and Google's `cmn`/Azure's `zh` both meaning Mandarin Chinese, aliased at the query layer only since the *stored* `locale` on a voice is also what gets sent back to that provider at generation time and must stay exact). Fish Audio's isn't synced yet (see ADR 0007's open items).
- `POST /voice-models` → `GET /voice-models` / `DELETE /voice-models/{id}` — voice cloning (ADR 0009, Fish Audio only). Training is multipart (a sample audio file + a name + an optional transcript), and turned out synchronous — `train_mode="fast"` (the only mode used; `"full"` mode's timing isn't verified, so isn't exposed) already returns `state: "trained"` in the create response, no polling needed, same shape as a TTS job. Free (`estimated_cost=0`, still through the ordinary hold->settle lifecycle for audit-trail parity) — ports the prior project's own real pricing (it never charged for cloning, only for *using* a clone). A trained voice's id then goes into `POST /generate/tts`'s `voice_model_id`, priced and routed exactly like a catalog voice.
- `GET /me` — current user + wallet balance; first call for a new Firebase identity bootstraps a local `users` row, a wallet, and the signup bonus.
- `PATCH /jobs/{id}` — mark a job public after the fact; `POST /generate/tts`'s `visibility` also does this at creation time, both set the same field ([ADR 0010](../docs/decisions/0010-public-gallery-visibility-flag.md)).
- `GET /gallery` — the public gallery: cursor-paginated `visibility: public` jobs with a ready asset, no auth dependency (`app/services/gallery.py`). `GET /jobs/{id}/asset` now lets any logged-in user through for a public job's asset, not just the owner.
- `/admin/*` — manual credit grants, job listing, settings read/write, capability-menu CRUD ([ADR 0012](../docs/decisions/0012-app-settings-table.md)). No `frontend/admin` UI yet — call these directly (`/docs`, curl, Postman).

Not implemented yet, by design (see [`docs/flows.md`](../docs/flows.md) for the full list): Kie adapter, whether Azure/Google support an equivalent to voice cloning (ADR 0009's own open item — Fish Audio is the only provider this covers), the stuck-job sweep half of the scheduled-task module ([ADR 0007](../docs/decisions/0007-scheduled-tasks-module.md) — catalog sync is done, the sweep isn't), real payment top-up, an actual scheduling mechanism for `sync_catalog.py` (manual for now).

Verified end-to-end against real infrastructure — Neon, Firebase, Fish Audio, R2, **and now real Azure Speech + Google Cloud TTS accounts**: sign in → submit a TTS job (all three providers, including Thai and Spanish voices for the target market) → real synthesis → real R2 upload → read the job back → mark it public → credits debited correctly. Catalog sync pulled 779 real Azure voices and 2066 real Google voices (82 distinct base languages after the cmn/zh merge below) on the last run. The frontend's "Select a voice" picker (`frontend/web/components/VoiceSheet.tsx`) is built and verified too — language dropdown (popular languages first, all 82 selectable, grouped by base language so e.g. "Spanish" pulls in both Azure's ~22 country locales and Google's 2, and "Chinese" pulls in both Azure's `zh-*` and Google's `cmn-*`), gender/provider filters, search, all against real synced data; picked voices actually route to the right provider end-to-end (confirmed with a Thai Google voice, a Mexican-Spanish Azure voice, and a Mandarin Google voice through real requests). Also caught and fixed: Azure locale codes with a third segment (`zh-CN-guangxi`, `sr-Latn-RS`, `iu-Cans-CA`) were all displaying as their base "{Language} ({Region})" name with the distinguishing part silently dropped — `frontend/web/lib/locale-names.ts` now parses script subtags and Azure's own dialect labels properly.

Audio Settings (speed/volume/pitch) verified end-to-end too, across real, non-default values in several requests: Azure (speed 0.7x/volume 30/pitch 20, and separately volume 75% via the actual browser UI), a Google Chirp3 HD voice (confirms the pitch-unsupported retry actually fires and still succeeds — both via a direct request and, separately, the real browser UI with pitch 30), and a Google Standard voice (pitch supported directly, no retry needed). The Fish Audio default path was verified too, before `voice_id` became required (speed 1.5x/pitch 85 via the actual browser UI) — the conversion logic itself hasn't changed since, only that this path is no longer reachable without an explicit voice.

The public gallery is verified end-to-end too: `GET /gallery` returns real public jobs with real pagination (`limit`/`next_cursor` tested against 8+ real rows); a non-owner logged-in user can fetch a public job's asset (200, real audio bytes) but still gets 404 on a private one; setting `visibility: "public"` at creation time (`POST /generate/tts`) makes a job appear in the gallery immediately, confirmed through the real browser (generate with "Share to Explore" on → the same job shows up on the Explore/Home page). The frontend also caught and fixed a real race condition here: switching between two gallery items' playback quickly could silently stop both, because the *previous* item's now-superseded `play()` promise rejects (`AbortError`, browser-standard behavior when `.src` changes mid-request) *after* the newly-clicked item's state was already set, and the original error handler blindly cleared `playingId` regardless of whose rejection it was — fixed by only clearing it if `playingId` still points at the item that failed.

Voice cloning (ADR 0009) is verified end-to-end against the real Fish Audio API and a real browser round trip (`/app/create/clone`): recorded/uploaded a sample → `POST /voice-models` (multipart) trained a real model → confirmed synchronous (`state: "trained"` in the create response itself, no polling — corrected an earlier assumption in architecture.md §3e that this needed Kie-style polling) → the new voice appeared in `GET /voice-models` immediately → generated real speech with it via `POST /generate/tts`'s `voice_model_id` (routed to Fish Audio, 7 credits charged at the ordinary per-character rate, real audio played back) → deleted it (`DELETE /voice-models/{id}`, 204). Training itself cost 0 credits, confirming the free-training decision works through the real hold→settle path. Caught and fixed a real bug along the way: deleting a voice model 503'd with a `ForeignKeyViolationError` — `jobs.voice_model_id`'s FK defaulted to Postgres's `RESTRICT`, which blocks the delete whenever any job (its own training job, or a TTS job that used it — always true) still references it; fixed with `ON DELETE SET NULL` (migration `0007`). Also observed: Fish Audio's own `DELETE /model/{id}` 404'd even though the model had been used successfully seconds earlier (an external quirk, not caught as a bug in this integration) — the best-effort design (log it, remove the local row regardless) meant this didn't block the user-facing delete, which is exactly what it's for.

**A second real incident, right after that first round of testing**: `voice_models` originally had no `title` column at all — `GET /voice-models` returned only `{id, provider, state, created_at}`, so every voice rendered as an identical, indistinguishable placeholder in the picker. That's exactly how a real user's just-trained voice got mistaken for leftover test data and deleted during a cleanup pass. Fixed by adding `title` (migration `0008`, backfilled from the name already typed into `POST /voice-models`' `title` form field, which was being sent to Fish Audio but never persisted on our own row) and making sure it's always rendered wherever a cloned voice is listed. The lesson generalizes past this one table: **a resource a person creates through the UI needs a stored, displayed name before anything (a person, or an agent) can safely tell instances of it apart** — a generic list of otherwise-identical rows is an invitation to delete the wrong one.

## Conventions (found the hard way — keep following them)

- **Every timestamp column is `DateTime(timezone=True)`** in `models/models.py`, matching `timestamptz` in the migrations. Omitting it compiles fine but fails at runtime the first time a tz-aware Python `datetime` (i.e. anything from `datetime.now(UTC)`, which is the only correct way to build one here) gets bound to that column.
- **Any route that writes data must `await db.commit()` explicitly before returning**, not rely on `get_db()`'s post-`yield` commit alone. In this FastAPI/Starlette combination, that generator-dependency cleanup can run *after* the response has already been sent — so a client that immediately re-reads what it just wrote (the normal "submit, then poll" pattern) can race the commit and see stale/missing data. Every existing write endpoint (`jobs.submit_tts`, `PATCH /jobs/{id}`, the `/admin/*` writes) already does this; keep the pattern for any new one.
- **A long-running `uvicorn --reload` process can silently stop picking up new files** — new routers/modules specifically, not just edits to existing ones. Caught this the hard way: a whole new router (`routes_catalog.py`) plus a changed request field (`reference_id` → `voice_id`) were added, `/health` kept responding fine, and a browser test even "passed" — because Pydantic silently ignores an unknown extra field, so the frontend's new `voice_id` was dropped and the request fell through to the *old* code's default behavior. **If a route added or changed this session 404s, or a change doesn't seem to take effect, don't trust the dev server — check `curl localhost:8000/openapi.json` for the route, and if it's missing, kill the process and restart it** rather than assuming the code is wrong.
- **A nullable FK needs its `ondelete` behavior stated explicitly, not left at Postgres's default `RESTRICT`** — `jobs.voice_model_id` was written as `ForeignKey("voice_models.id")` with no `ondelete`, which compiles and migrates fine and only breaks the first time someone actually deletes a referenced row (`DELETE /voice-models/{id}` 503'd, real bug caught via a real browser test — see ADR 0009). If a nullable reference is meant to survive the thing it points to being deleted (a job's history outliving a voice the user later removes), say `ondelete="SET NULL"` on the column *and* match it in the migration's `op.create_foreign_key(..., ondelete=...)` — SQLAlchemy's own default is `NO ACTION`/`RESTRICT`, not "leave the reference dangling."

## Tests / linting

```bash
ruff check app migrations
pytest   # none written yet
```
