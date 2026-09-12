# ADR 0007: Scheduled/Batch Task Module

- Status: Accepted
- Date: 2026-09-11

## Context

Deciding to periodically sync provider voice/model catalogs (Azure, Google, Fish Audio's official voices) into our own database — rather than querying providers live on every request, which would add external-API latency to a high-frequency user interaction (picking a voice), conflicting with the product priority in [product-scope.md §0](../product-scope.md) — requires something that runs on a schedule, not in response to a user request.

A second, independently-arrived-at need turns out to be the same kind of thing: a Kie job that never reaches a terminal state — no webhook arrives, and polling exceeds the 10–15 minute policy already noted in [architecture.md §3d](../architecture.md) — needs to be swept and marked `failed` (with its credit hold released, [ADR 0003](0003-credit-ledger-hold-then-settle.md)). Nothing about a user's own requests naturally triggers that check.

Both are instances of the same requirement: **periodic, backend-initiated work that isn't triggered by an inbound API request.**

## Decision

A scheduled/batch task module exists in the backend, responsible for:
1. **Provider catalog sync** — pulling each provider's voice/model list (Azure, Google, Fish Audio's official voices — not their public community catalog, [product-scope.md §1.2](../product-scope.md)) into our own database on a recurring schedule. Frequency and the exact source endpoint per provider are implementation details decided per-provider when that adapter is built, not here.
2. **Stuck-job sweep** — periodically finding jobs stuck in `pending`/`processing` past a timeout and resolving them to `failed`, releasing their credit hold.

This lives in the backend codebase (`backend/app/scheduled/`, alongside `providers/`, `services/`, `api/`) as plain callable functions/services — the same `services/` and `providers/` code a request handler would call, just invoked by a scheduler instead of a route. **The scheduling mechanism itself (in-process scheduler, an external cron trigger hitting an internal endpoint, a managed queue's scheduled-job feature, etc.) is an open implementation choice**, deferred until backend hosting is decided — whatever triggers these functions, the functions themselves don't change.

## Alternatives considered

- **Sync catalogs / sweep jobs lazily, triggered by the next relevant user request** (e.g. sync Azure's catalog the next time someone opens the voice picker if it's stale). Rejected: reintroduces exactly the latency-on-the-user's-request problem periodic sync was meant to avoid, and a stuck job needs to resolve even if the affected user never comes back to check on it (their held credits would stay locked indefinitely otherwise).
- **A full task-queue system (Celery, etc.) decided now.** Rejected as premature at the time — the actual scheduling/execution mechanism depended on where the backend ends up hosted, which wasn't decided yet; picking the mechanism then risked a choice that didn't fit that hosting decision. (Later adopted anyway, for a different and independently-arrived-at reason — see [ADR 0014](0014-background-job-execution.md): decoupling provider calls from the request path, not scheduling, is what actually forced the choice.)

## Consequences

**Positive:** the voice picker and generation flows never pay live-provider-API latency for catalog data (product priority upheld); stuck jobs and their held credits get resolved even if the user never returns to that session; the module's responsibilities are decided now so nothing gets built assuming synchronous-only backend behavior.

**Negative / open items:**
- ~~Scheduling mechanism is explicitly undecided~~ **Resolved by [ADR 0014](0014-background-job-execution.md)**: arq's cron feature (adopted there for a different, independently-arrived-at reason — decoupling provider calls from the request path) turned out to be this module's scheduling mechanism too. The stuck-job sweep described below is now implemented as an arq cron job (`app/worker/cron.py`, every 5 minutes); `sync_catalog.py` can move to one too once a sync cadence is picked, but still runs manually (`python -m app.scheduled.sync_catalog`) for now — nothing forces that particular move yet.
- **Per-provider sync — Azure and Google decided and implemented**, verified against real credentials: Azure's `GET .../voices/list` and Google's `GET /v1/voices` (`backend/app/providers/azure.py`/`google.py`'s `list_voices()`). **Fish Audio still undecided** — no "official voices" list endpoint has been verified for it yet, so it's left out of `voice_catalog` rather than guessed at (its TTS flow still works via a raw `provider_voice_id`, e.g. for cloned voices, ADR 0009 — just outside the picker for now). Sync frequency (how often to re-run) is still unset for either provider — manual triggering is enough for the current slice.
- ~~Sweep timeout threshold... and the sweep itself isn't implemented yet~~ **The sweep is now implemented** (`app/worker/cron.py sweep_stuck_jobs`, [ADR 0014](0014-background-job-execution.md)) — the threshold itself (currently 15 minutes, Kie's own polling-guidance figure reused as a starting point, not tuned against real data) is still open.
