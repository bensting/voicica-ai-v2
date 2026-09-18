# API Contract

The backend's HTTP surface, consumed identically by `frontend/web` (marketing, product app, and admin alike) and `android/` ([ADR 0005](decisions/0005-frontend-surfaces.md)/[ADR 0020](decisions/0020-admin-folded-into-web.md)). This is mostly a direct consequence of decisions already made elsewhere — endpoints aren't re-argued here, they're assembled from the ADRs and linked back to them. Where something genuinely needed a fresh call, it's marked.

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

### Billing (credit purchases, [ADR 0024](decisions/0024-credit-purchases-stripe-checkout.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /billing/packages` | required | The current sellable credit packs (`app_settings.credit_packages`) — `{key, label, credits, price_usd_cents}` each. Three real rows today: `small`/`medium`/`large`. |
| `POST /billing/checkout` | required | `{package_key}` → `{checkout_url}`, a real Stripe Checkout Session (one-time payment, never a subscription). The browser is redirected to `checkout_url` directly — no Stripe.js/publishable key needed for this flow. A `credit_purchases` row is created `pending` before this returns, so the webhook below always has something to find. Credits land only once `POST /webhooks/stripe` confirms the payment, not at session-creation time. **Built, not yet verified against a real Stripe test-mode payment** — see ADR 0024's own open items. |

### Submitting a capability (one endpoint per capability, per [ADR 0002](decisions/0002-unified-async-job-model.md)/[architecture.md §3](architecture.md))

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /generate/tts` | required | Text-to-speech — `{text, voice_id or voice_model_id, speed, volume, pitch, visibility}`. **Exactly one of `voice_id`/`voice_model_id` is required** (enforced by a `schemas.TTSRequest` validator) — `voice_id` is a `GET /catalog/voices` row's id, `voice_model_id` is a `GET /voice-models` row's id (a user's own cloned voice, [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md), **implemented**). Fish Audio isn't a general fallback voice — it's reserved for cloned voices — so there is no default voice to fall back to without one. Picking a voice picks the provider either way — Azure/Google/Fish Audio are routed to automatically based on which row was resolved, never a separate provider field (architecture.md §3c). `speed`/`volume`/`pitch` are one scale across every provider (`speed` 0.5-2.0x default 1.0; `volume`/`pitch` 1-100 default 50), all optional — each adapter converts to its own units server-side (see `services/jobs.py submit_tts`'s docstring for the exact, verified-in-production formulas); Fish Audio has no pitch control and silently ignores that field. `visibility` (`private` default | `public`, [ADR 0010](decisions/0010-public-gallery-visibility-flag.md)) lets a user opt into the gallery at creation time, in addition to `PATCH /jobs/{id}` afterward — both set the same field, neither replaces the other. |
| `POST /generate/kie` | required | **Implemented and verified.** One generic endpoint for every Kie model, regardless of category (two image categories today; video/music once catalogued — [ADR 0015](decisions/0015-kie-model-catalog.md)) — `{model_id, inputs, visibility, uploaded_r2_keys}`. `model_id` is a `GET /kie/models` row's id and picks the category (`Job.capability`) automatically, the same way TTS's `voice_id` picks a provider; `inputs` is passed to Kie's own `input` object verbatim, shaped by that model's `input_schema` (see below) — an `image`-type field's value is a URL (or array of URLs) from `POST /kie/uploads`, never a raw file. `uploaded_r2_keys` (optional, [ADR 0016](decisions/0016-kie-image-to-image-uploads.md)) lists any upload(s) this job's `inputs` references, so the backend can delete them once the job reaches a terminal state — empty/omitted for a text-to-image job. Genuinely async under the hood (unlike every synchronous TTS provider): the response is `202 pending`, then `processing` once the worker's submit-only task calls Kie's `createTask` — poll `GET /jobs/{id}` same as any other job; completion arrives via `POST /webhooks/kie` or a 1-minute poll-sweep cron, whichever comes first. |
| `POST /voice-models` | required | **Implemented and verified.** Train a reusable voice (creates a `voice_model_training` job — [ADR 0009](decisions/0009-voice-cloning-reusable-asset.md)). Multipart, not JSON (it carries a file): `title` (form field, 1-50 chars), `reference_text` (form field, optional — the sample's transcript, improves cloning quality), `audio` (the sample file). Returns a `JobResponse` like every other submission — training turned out synchronous (Fish Audio's `train_mode="fast"`, verified against the real API: `state: "trained"` already in the create response, no polling needed), so it's already terminal, same as a TTS job; `output.voice_model_id` is the new `voice_models` row's id once it succeeds. **Free** (`estimated_cost=0`) — ports the prior project's own real pricing (see ADR 0009). |

Each returns `202 { "job_id": "...", "status": "pending" }` immediately and genuinely pending — the actual provider call happens in a background worker, never inline in the request ([ADR 0014](decisions/0014-background-job-execution.md); see [architecture.md §3c/§3f](architecture.md)). Poll `GET /jobs/{id}` until a terminal status. (Before ADR 0014, a synchronous provider's — Azure/Google/Fish Audio TTS — job was already `succeeded` in this same response; that's no longer true for any provider, sync or async, now that the vendor call itself moved off the request path.)

**`POST /generate/kie` verified end-to-end against real infrastructure**, not just wired up: submitted a real `flux-2/pro-text-to-image` job -> `202 pending` in ~milliseconds -> the `queue:kie-submit` worker called Kie's real `createTask` (~6s round trip) and the job moved to `processing` with a real `provider_job_id` -> polled Kie's real `recordInfo` -> `succeeded` with a real image -> mirrored into R2 (`GET /jobs/{id}/asset` serves it) -> wallet correctly debited exactly `5` credits, matching Kie's own reported `creditsConsumed` (settlement is 1:1 from that number, [ADR 0015](decisions/0015-kie-model-catalog.md), not re-derived). A first attempt (missing an as-yet-unconfirmed required `resolution` field) also verified the failure path for real: Kie rejected it, the job correctly ended `failed` with its hold fully released — no charge, same guarantee as every other provider. **Image-to-image verified the same way** ([ADR 0016](decisions/0016-kie-image-to-image-uploads.md)): a real uploaded photo, transformed by a real `flux-2/pro-image-to-image` call per the requested edit (inspected, not just assumed), settled correctly, with the uploaded reference confirmed deleted from R2 right after.

Separate endpoints per capability (not one generic `POST /jobs`) so each gets its own Pydantic request schema — a video request's `duration`/`resolution` shouldn't be optional fields on a shape shared with TTS's `text`/`voice_id`.

### Jobs (generic — shared across every capability)

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /jobs/{id}` | required, owner only | Poll one job to completion ([architecture.md §3b](architecture.md)) |
| `GET /jobs` | required | Current user's job history, filterable by `capability`/`status` |
| `PATCH /jobs/{id}` | required, owner only | `{ "visibility": "public" }` — the only field this can change ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)) |
| `GET /jobs/{id}/asset` | required — owner, **or any logged-in user if the job is public** | Streams the job's generated file. A succeeded job's `output.asset_url` is a relative path to *this* endpoint, not a raw R2 URL — the backend proxies the bytes rather than presigning, because presigned R2 GET URLs from this environment's botocore reject with "Missing x-amz-content-sha256" (a real, verified incompatibility, not a config choice — see `services/assets.py`). Now that the public gallery exists ([ADR 0010](decisions/0010-public-gallery-visibility-flag.md)), ownership alone doesn't gate this — a `visibility: public` job's asset is playable by anyone signed in, not just its creator. Still not truly anonymous-accessible (Explore lives inside `(app)`'s login gate for now); revisit if a fully public, unauthenticated gallery page is ever built. |
| `GET /events?token=` | required — token as a query param, not the usual `Authorization` header (the browser's native `EventSource` can't set custom headers) | **Implemented and verified.** [ADR 0018](decisions/0018-realtime-job-updates-sse.md) — Server-Sent Events; one persistent connection per user, forwarding `{job_id, status, capability}` the instant any of that user's own jobs reaches a terminal state (pushed via Redis pub/sub from whichever worker process actually finished it). Not a replacement for `GET /jobs`/`GET /jobs/{id}` — this only signals "something changed," the client still re-fetches the real row. |

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
| `GET /kie/categories` | required | **Implemented and verified.** Enabled Kie categories — `{id, display_name, output_type}` each. `output_type` (`image`/`video`/`audio`) tells the frontend which result-renderer a category's jobs need. Two real rows: `text-to-image`, `image-to-image` ([ADR 0016](decisions/0016-kie-image-to-image-uploads.md)). |
| `GET /kie/models?category_id=` | required | **Implemented and verified.** Enabled Kie models, optionally filtered to one category — `{model_id, category_id, display_name, input_schema, pricing}` each. `input_schema` drives a generic, schema-rendered form (no per-model frontend code); `pricing` lets the frontend show a live cost estimate as the user picks values, the way Kie's own playground does ([ADR 0015](decisions/0015-kie-model-catalog.md)). Five field `type`s exist now: `text`/`select`/`number`/`boolean`/`image` — the last one's value is a URL (or array, `multiple`/`max`) from `POST /kie/uploads`, verified rendering correctly for a real model with zero page-specific code. |
| `GET /kie/models/{model_id}` | required | **Implemented and verified.** One model's full schema, for the generation page's direct fetch (works whether reached via the list page or a deep link/refresh). `model_id` may contain a literal `/` (e.g. `flux-2/pro-image-to-image`) — the route uses a `:path` converter, verified against a real request. |
| `POST /kie/uploads` | required | **Implemented and verified end-to-end against real infrastructure.** `multipart/form-data`, one `file` (PNG/JPEG/WebP, ≤15MB) → `{url, r2_key}`. `url` is a short-lived public R2 URL only Kie's servers ever need to fetch ([ADR 0016](decisions/0016-kie-image-to-image-uploads.md)) — deleted the moment the job that ends up using it reaches a terminal state, not kept for the usual 90-day output-retention window. A real upload → real `flux-2/pro-image-to-image` call → Kie genuinely fetched and used it (verified by inspecting the transformed result) → the upload confirmed gone from R2 immediately after settlement. Returns `503 upload_unavailable` if `R2_PUBLIC_BASE_URL` isn't configured, rather than silently handing back a URL Kie could never actually reach. |

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
| `GET /gallery?cursor=&limit=&output_type=` | **public** | **Implemented and verified.** Cursor-paginated `visibility: public` jobs with a ready asset, newest first. `next_cursor` is the last item's `created_at` (ISO 8601, not opaque — nothing here is sensitive); pass it back as `?cursor=` for the next page, `null` means no more. `limit` defaults to 20, capped at 50. `output_type` (`audio`/`image`/`video`, optional) backs Explore's Voices/Images/Videos tabs — reuses `kie_categories.output_type` (ADR 0017) rather than a second classification; TTS jobs (`capability="tts"`, not a Kie category) are explicitly `audio`. Response items (`GalleryItemResponse`) are deliberately leaner than `JobResponse` — no cost/error/visibility fields, no creator identity. `GET /jobs/{id}/asset` allows any logged-in user through for a public job's audio, not just the owner (still requires *some* login for now — Explore lives inside `(app)`, not a truly anonymous page yet). |

### Provider-facing (not called by any client)

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /webhooks/kie` | none — see below | **Implemented and verified** (the poll-based path it shares logic with was exercised for real; the HTTP callback itself needs a public URL to test, not yet set up in local dev). Kie's `callBackUrl` target ([architecture.md §3d](architecture.md), [ADR 0015](decisions/0015-kie-model-catalog.md)). Kie documents no signature/secret scheme for this, so this endpoint trusts only `taskId` to find *a* job, then re-derives everything from a real `recordInfo` poll rather than the callback body — a forged/replayed call can trigger a harmless extra poll at worst, never fabricate a result or move credits. |
| `POST /webhooks/stripe` | Stripe signature (`Stripe-Signature` header, verified via `stripe.Webhook.construct_event` against `STRIPE_WEBHOOK_SECRET`) | [ADR 0024](decisions/0024-credit-purchases-stripe-checkout.md). The opposite trust posture from Kie's webhook above: the signature-verified body *is* trusted (there's no equivalent independent re-poll for a Checkout Session). On `checkout.session.completed`, credits the matching `credit_purchases` row's wallet exactly once — `SELECT ... FOR UPDATE` on that row makes a redelivered event (Stripe's delivery is at-least-once) a safe no-op. **Built, not yet exercised against a real Stripe test-mode event.** |

### Admin

An `(admin)` route group inside `frontend/web`, not a separate app ([ADR 0020](decisions/0020-admin-folded-into-web.md)) — own route namespace, gated by `users.role`. Full feature scope still deferred by request:

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
| `POST /admin/kie-categories` | admin role | **Implemented and verified.** Add a Kie category (`id, display_name, output_type, enabled`) |
| `POST /admin/kie-models` | admin role | **Implemented and verified.** Add a Kie model (`model_id, category_id, display_name, input_schema, pricing, enabled`) — this, alone, is what "add a new Kie model" means end to end ([ADR 0015](decisions/0015-kie-model-catalog.md)): no other endpoint or deploy involved. |
| `PATCH /admin/kie-models/{model_id}` | admin role | **Implemented and verified.** Partial update — used live to fix a real model's `input_schema` after a live test surfaced a missing required field, with no restart needed. |
| `DELETE /admin/kie-models/{model_id}` | admin role | **Implemented and verified.** Remove a model |

## Open items

- Whether `/catalog/*` should actually be public (no real sensitivity, just defaulting to the general auth stance) — soft call, not blocking.
- Pagination page size defaults/limits — implementation detail.
- Admin's endpoints — blocked on Admin's feature scope being picked back up.
