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
| `POST /generate/tts` | required | Text-to-speech — `{text, voice_id}`. `voice_id` is a `GET /catalog/voices` row's id; omit it for the default voice (Fish Audio). Picking a voice picks the provider — Azure/Google/Fish Audio are routed to automatically based on which voice's `voice_id` was sent, never a separate provider field (architecture.md §3c). |
| `POST /generate/image` | required | Kie image generation |
| `POST /generate/music` | required | Kie music generation |
| `POST /generate/video` | required | Kie video generation |
| `POST /voice-models` | required | Train a reusable voice (creates a `voice_model_training` job — [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md)) |

Each returns `202 { "job_id": "...", "status": "pending" }` immediately — including the synchronous providers (Azure/Google/Fish Audio TTS), whose job is already `succeeded` in that same response ([ADR 0002](decisions/0002-unified-async-job-model.md); see [architecture.md §3c](architecture.md)).

Separate endpoints per capability (not one generic `POST /jobs`) so each gets its own Pydantic request schema — a video request's `duration`/`resolution` shouldn't be optional fields on a shape shared with TTS's `text`/`voice_id`.

### Jobs (generic — shared across every capability)

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /jobs/{id}` | required, owner only | Poll one job to completion ([architecture.md §3b](architecture.md)) |
| `GET /jobs` | required | Current user's job history, filterable by `capability`/`status` |
| `PATCH /jobs/{id}` | required, owner only | `{ "visibility": "public" }` — the only field this can change ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)) |
| `GET /jobs/{id}/asset` | required, owner only | Streams the job's generated file. A succeeded job's `output.asset_url` is a relative path to *this* endpoint, not a raw R2 URL — the backend proxies the bytes rather than presigning, because presigned R2 GET URLs from this environment's botocore reject with "Missing x-amz-content-sha256" (a real, verified incompatibility, not a config choice — see `services/assets.py`). Revisit if that gets resolved upstream; until a public gallery exists ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)), this stays owner-only like everything else here. |

### Voice models (persisted asset, [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /voice-models` | required | List the user's own trained (`ready`) voices |
| `DELETE /voice-models/{id}` | required, owner only | Delete an owned voice |

(Training goes through `POST /voice-models` above and is polled via `GET /jobs/{id}` like any other job — no separate poll endpoint.)

### Catalog (read-only reference data)

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /catalog/voices?provider=&locale=` | required | Synced voice list (`voice_catalog`, [ADR 0007](decisions/0007-scheduled-tasks-module.md)) — **Azure and Google implemented and verified** (779 + 2066 voices synced from their real APIs, including full th-TH/id-ID/es-* coverage); Fish Audio isn't in the catalog yet (no verified "official voices" list endpoint for it — see `backend/README.md`). **With no `locale` given, defaults to the target market only** (th/id/es prefixes, ~266 voices) rather than the full multi-language catalog — pass an explicit `locale` to see anything outside it. Sync is manual for now (`python -m app.scheduled.sync_catalog`) — the actual scheduling mechanism is still ADR 0007's open item. Consumed by `frontend/web/components/VoiceSheet.tsx`, verified end-to-end. |
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
| `GET /gallery` | **public** | Paginated `visibility: public` jobs with a ready asset |

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
