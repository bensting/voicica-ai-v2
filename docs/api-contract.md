# API Contract

The backend's HTTP surface, consumed identically by `frontend/web`, `frontend/admin`, and `android/` ([ADR 0005](decisions/0005-frontend-surfaces.md)). This is mostly a direct consequence of decisions already made elsewhere — endpoints aren't re-argued here, they're assembled from the ADRs and linked back to them. Where something genuinely needed a fresh call, it's marked.

## Conventions

- **Auth**: `Authorization: Bearer <Firebase ID token>`, verified via `core/auth.py` ([ADR 0008](decisions/0008-auth-provider.md)). Endpoints marked "public" skip this.
- **Errors**: `{ "error": { "code": "insufficient_credits", "message": "..." } }` with a stable machine-readable `code`, not just an HTTP status — the frontend needs to branch on *why* a request failed (out of credits vs. invalid input vs. provider down) to show a precise, friendly message, not a generic failure state. Ties back to [product-scope.md §0](product-scope.md): a vague error is a UX cost.
- **Single-resource responses**: the resource itself, no wrapping envelope (`{ "id": ..., "status": ... }`, not `{ "data": { ... } }`).
- **List responses**: cursor-paginated — `{ "items": [...], "next_cursor": "..." | null }`. Cursor over offset because job/gallery history grows and offset pagination degrades and can skip/duplicate rows under concurrent writes.

## Endpoints

### Identity / wallet

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /me` | required | Current user profile + wallet balance |
| `GET /wallet/transactions` | required | Paginated credit ledger ([`credit_transactions`](data-model.md), ADR 0003) |

### Submitting a capability (one endpoint per capability, per [ADR 0002](decisions/0002-unified-async-job-model.md)/[architecture.md §3](architecture.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /generate/tts` | required | Text-to-speech — `{text, voice_id or voice_model_id, speed, volume, pitch, visibility}`. **Exactly one of `voice_id`/`voice_model_id` is required** (enforced by a `schemas.TTSRequest` validator) — `voice_id` is a `GET /catalog/voices` row's id, `voice_model_id` is a `GET /voice-models` row's id (a user's own cloned voice, [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md), **implemented**). Fish Audio isn't a general fallback voice — it's reserved for cloned voices — so there is no default voice to fall back to without one. Picking a voice picks the provider either way — Azure/Google/Fish Audio are routed to automatically based on which row was resolved, never a separate provider field (architecture.md §3c). `speed`/`volume`/`pitch` are one scale across every provider (`speed` 0.5-2.0x default 1.0; `volume`/`pitch` 1-100 default 50), all optional — each adapter converts to its own units server-side (see `services/jobs.py submit_tts`'s docstring for the exact, verified-in-production formulas); Fish Audio has no pitch control and silently ignores that field. `visibility` (`private` default | `public`, [ADR 0010](decisions/0010-public-gallery-visibility-flag.md)) lets a user opt into the gallery at creation time, in addition to `PATCH /jobs/{id}` afterward — both set the same field, neither replaces the other. |
| `POST /generate/image` | required | Kie image generation |
| `POST /generate/music` | required | Kie music generation |
| `POST /generate/video` | required | Kie video generation |
| `POST /voice-models` | required | **Implemented and verified.** Train a reusable voice (creates a `voice_model_training` job — [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md)). Multipart, not JSON (it carries a file): `title` (form field, 1-50 chars), `reference_text` (form field, optional — the sample's transcript, improves cloning quality), `audio` (the sample file). Returns a `JobResponse` like every other submission — training turned out synchronous (Fish Audio's `train_mode="fast"`, verified against the real API: `state: "trained"` already in the create response, no polling needed), so it's already terminal, same as a TTS job; `output.voice_model_id` is the new `voice_models` row's id once it succeeds. **Free** (`estimated_cost=0`) — ports the prior project's own real pricing (see ADR 0009). |

Each returns `202 { "job_id": "...", "status": "pending" }` immediately — including the synchronous providers (Azure/Google/Fish Audio TTS), whose job is already `succeeded` in that same response ([ADR 0002](decisions/0002-unified-async-job-model.md); see [architecture.md §3c](architecture.md)).

Separate endpoints per capability (not one generic `POST /jobs`) so each gets its own Pydantic request schema — a video request's `duration`/`resolution` shouldn't be optional fields on a shape shared with TTS's `text`/`voice_id`.

### Jobs (generic — shared across every capability)

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /jobs/{id}` | required, owner only | Poll one job to completion ([architecture.md §3b](architecture.md)) |
| `GET /jobs` | required | Current user's job history, filterable by `capability`/`status` |
| `PATCH /jobs/{id}` | required, owner only | `{ "visibility": "public" }` — the only field this can change ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)) |
| `GET /jobs/{id}/asset` | required — owner, **or any logged-in user if the job is public** | Streams the job's generated file. A succeeded job's `output.asset_url` is a relative path to *this* endpoint, not a raw R2 URL — the backend proxies the bytes rather than presigning, because presigned R2 GET URLs from this environment's botocore reject with "Missing x-amz-content-sha256" (a real, verified incompatibility, not a config choice — see `services/assets.py`). Now that the public gallery exists ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)), ownership alone doesn't gate this — a `visibility: public` job's asset is playable by anyone signed in, not just its creator. Still not truly anonymous-accessible (Explore lives inside `(app)`'s login gate for now); revisit if a fully public, unauthenticated gallery page is ever built. |

### Voice models (persisted asset, [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /voice-models` | required | **Implemented and verified.** List the user's own trained (`ready`) voices — `{id, title, provider, state, created_at}` each. `title` (the name given at training time) was added after a real incident: without it, every voice was an identical, indistinguishable placeholder in the picker, and that's exactly how someone else's real cloned voice got mistaken for test data and deleted — always render it. |
| `DELETE /voice-models/{id}` | required, owner only | **Implemented and verified.** Delete an owned voice — 204, permanent. Deletes at the provider too (best-effort: a failure there is logged and doesn't block removing the local row — verified with a real case, see below). |

(Training goes through `POST /voice-models` above and is polled via `GET /jobs/{id}` like any other job — no separate poll endpoint, since it's synchronous in practice.)

Verified end-to-end against the real Fish Audio API and a real browser round trip: train a voice from a short sample -> it appears in `GET /voice-models` as `ready` immediately -> generate speech with it via `POST /generate/tts`'s `voice_model_id` (routed to Fish Audio, priced as ordinary TTS, real audio played back) -> delete it (Fish Audio's own `DELETE /model/{id}` 404'd in this run even though the model had just been used successfully seconds earlier — an observed real quirk, not a bug in this integration; the best-effort design meant the local row was removed regardless, exactly as intended). Also caught and fixed a real bug this surfaced: `jobs.voice_model_id`'s FK needs `ON DELETE SET NULL` (migration `0007`) — Postgres's default `RESTRICT` made deleting a voice model 503 whenever any job (its own training job, or a TTS job that used it) still referenced it, which is always, since one always does.

### Catalog (read-only reference data)

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /catalog/voices?provider=&locale=&language=` | required | Synced voice list (`voice_catalog`, [ADR 0007](decisions/0007-scheduled-tasks-module.md)) — **Azure and Google implemented and verified** (779 + 2066 voices synced from their real APIs, 82 distinct base languages, every language either provider supports — no target-market restriction; product-scope.md's target market is an infra-region decision, not a restriction on which languages a user can pick, see `services/voice_catalog.py`'s module docstring for the correction). `language` (e.g. `es`) matches every locale variant of that base language across every provider, alias-aware — Google labels Mandarin Chinese `cmn`, Azure labels the same language `zh`, so `language=zh` includes both; the stored `locale` on each returned voice is always the provider's own real value (`cmn-CN` stays `cmn-CN`, never rewritten to `zh-CN` — Google's API 400s on a mismatched languageCode). `locale` stays as an exact match for anything that wants one specific variant. Fish Audio isn't in the catalog yet (no verified "official voices" list endpoint for it — see `backend/README.md`). Sync is manual for now (`python -m app.scheduled.sync_catalog`) — the actual scheduling mechanism is still ADR 0007's open item. The picker always passes an explicit `language` (one language's voices are ~10-220 rows; the full catalog is 2800+) — see the next row. |
| `GET /catalog/languages?provider=` | required | Every base language actually in the catalog, each with its voice count across every provider/locale variant combined — populates the picker's language dropdown without fetching every voice just to read off `.locale`. Both consumed by `frontend/web/components/VoiceSheet.tsx`, verified end-to-end. |
| `GET /catalog/kie-models?capability=` | required | Kie's curated model catalog + pricing ([ADR 0001](decisions/0001-provider-adapter-layer.md)) |

Both required-auth for now by default consistency with everything else being gated — neither is sensitive data, so this is a soft call, easy to open up later if there's a reason to (e.g. showing the catalog on a marketing page).

### Capability menu (drives the "+" button, [ADR 0012](decisions/0012-app-settings-table.md))

The frontend has no hardcoded list of capabilities ("+" opens a sheet, not a set of hrefs baked into a component) — it renders whatever this returns, already resolved to one locale. The one thing the frontend still owns locally is a small icon-key → SVG lookup table (`icon` below is a key into that, not markup).

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /config/menu?locale=` | required | Enabled items, ordered, resolved to `locale` (`th`/`id`/`es`/`en`, falls back to `en`) — each `{ "id", "icon", "route", "badge", "label", "description" }` |

Backed by a single `app_settings` row (key `capability_menu`, a JSON array — not a dedicated table, per ADR 0012's "structured multi-item config" case) holding every locale's labels/descriptions per item plus `enabled`/`order`; admins manage it item-by-item below rather than PATCHing the raw blob, since a hand-edited JSON array of multi-locale strings is easy to corrupt.

### Gallery ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /gallery?cursor=&limit=` | **public** | **Implemented and verified.** Cursor-paginated `visibility: public` jobs with a ready asset, newest first. `next_cursor` is the last item's `created_at` (ISO 8601, not opaque — nothing here is sensitive); pass it back as `?cursor=` for the next page, `null` means no more. `limit` defaults to 20, capped at 50. Response items (`GalleryItemResponse`) are deliberately leaner than `JobResponse` — no cost/error/visibility fields, no creator identity. `GET /jobs/{id}/asset` allows any logged-in user through for a public job's audio, not just the owner (still requires *some* login for now — Explore lives inside `(app)`, not a truly anonymous page yet). |

### Provider-facing (not called by any client)

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /webhooks/kie` | Kie's own signature/secret, not Firebase | Kie's `callBackUrl` target ([architecture.md §3d](architecture.md)) |

### Admin

Separate app/deployment ([ADR 0005](decisions/0005-frontend-surfaces.md)), own route namespace, gated by `users.role`. Full feature scope still deferred by request — but the current slice needs a minimal set, callable via script for now (no `frontend/admin` UI yet):

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /admin/users/{id}` | admin role | Look up a user (for support/debugging) |
| `POST /admin/users/{id}/credits` | admin role | Manually adjust a user's balance (`{amount, reason}`) — the stopgap for not having real top-up yet |
| `GET /admin/jobs` | admin role | List jobs across all users, filterable (debugging/monitoring) |
| `GET /admin/settings` | admin role | Read all `app_settings` |
| `PATCH /admin/settings/{key}` | admin role | Update one tunable value ([ADR 0012](decisions/0012-app-settings-table.md)) |
| `GET /admin/menu` | admin role | List every capability-menu item, including disabled ones, all locales |
| `POST /admin/menu` | admin role | Add an item (`id, icon, route, enabled, order, badge, labels{}, descriptions{}`) |
| `PATCH /admin/menu/{item_id}` | admin role | Partial update (any subset of the fields above) |
| `DELETE /admin/menu/{item_id}` | admin role | Remove an item |

## Open items

- Whether `/catalog/*` should actually be public (no real sensitivity, just defaulting to the general auth stance) — soft call, not blocking.
- Pagination page size defaults/limits — implementation detail.
- Admin's endpoints — blocked on Admin's feature scope being picked back up.
