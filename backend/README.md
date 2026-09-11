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

## Run migrations

```bash
alembic upgrade head
```

This creates the schema ([`docs/data-model.md`](../docs/data-model.md)) and seeds `app_settings`' placeholder values ([ADR 0012](../docs/decisions/0012-app-settings-table.md)).

## Run the app

```bash
uvicorn app.main:app --reload --port 8000
```

Or in PyCharm: the **"Backend"** run configuration (`.run/Backend.run.xml`, checked into the repo) runs the same command — pick it from the run-configuration dropdown. It uses the module's configured Python interpreter rather than a hardcoded path, so first set the project interpreter to `backend/.venv` (Settings → Project → Python Interpreter → Add → Existing → `backend/.venv/Scripts/python.exe`) if you haven't already.

Then `GET http://localhost:8000/health` should return `{"status": "ok"}`, and `http://localhost:8000/docs` has the interactive OpenAPI UI — every route needs a Firebase ID token as a bearer token except `/health`.

## What's implemented (this slice)

- `POST /generate/tts` → `GET /jobs/{id}` / `GET /jobs` — submit and read back a Fish Audio TTS job, credits held/settled/released around it ([ADR 0002](../docs/decisions/0002-unified-async-job-model.md), [ADR 0003](../docs/decisions/0003-credit-ledger-hold-then-settle.md)).
- `GET /me` — current user + wallet balance; first call for a new Firebase identity bootstraps a local `users` row, a wallet, and the signup bonus.
- `PATCH /jobs/{id}` — mark a job public ([ADR 0010](../docs/decisions/0010-public-gallery-visibility-flag.md)).
- `/admin/*` — manual credit grants, job listing, settings read/write ([ADR 0012](../docs/decisions/0012-app-settings-table.md)). No `frontend/admin` UI yet — call these directly (`/docs`, curl, Postman).

Not implemented yet, by design (see [`docs/flows.md`](../docs/flows.md) for the full list): Azure/Google/Kie adapters, voice cloning ([ADR 0009](../docs/decisions/0009-voice-cloning-reusable-asset.md)), the scheduled-task module ([ADR 0007](../docs/decisions/0007-scheduled-tasks-module.md)), real payment top-up.

Verified end-to-end against a real Neon database, Firebase project, Fish Audio account, and R2 bucket: sign in → submit a TTS job → real Fish Audio synthesis → real R2 upload → read the job back → mark it public → credits debited correctly.

## Conventions (found the hard way — keep following them)

- **Every timestamp column is `DateTime(timezone=True)`** in `models/models.py`, matching `timestamptz` in the migrations. Omitting it compiles fine but fails at runtime the first time a tz-aware Python `datetime` (i.e. anything from `datetime.now(UTC)`, which is the only correct way to build one here) gets bound to that column.
- **Any route that writes data must `await db.commit()` explicitly before returning**, not rely on `get_db()`'s post-`yield` commit alone. In this FastAPI/Starlette combination, that generator-dependency cleanup can run *after* the response has already been sent — so a client that immediately re-reads what it just wrote (the normal "submit, then poll" pattern) can race the commit and see stale/missing data. Every existing write endpoint (`jobs.submit_tts`, `PATCH /jobs/{id}`, the `/admin/*` writes) already does this; keep the pattern for any new one.

## Tests / linting

```bash
ruff check app migrations
pytest   # none written yet
```
