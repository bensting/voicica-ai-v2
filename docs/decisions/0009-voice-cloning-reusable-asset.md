# ADR 0009: Voice Cloning Produces a Reusable, User-Owned Voice Asset

- Status: Accepted
- Date: 2026-09-11

## Context

Investigating Fish Audio's API ([architecture.md §3e](../architecture.md)) showed voice cloning is naturally two-stage there: train a voice once (async), then speak with it any number of times (sync), via the resulting model id. This raised an open question in [product-scope.md §1.2](../product-scope.md): should the product treat a cloned voice as a durable, reusable asset, or as a one-shot byproduct of a single generation? **Confirmed: reusable — a cloned voice is the user's asset**, not a one-time output.

## Decision

A `voice_models` table holds one row per cloned voice a user owns: `id`, `user_id` FK, `provider`, `provider_model_id`, `state` (`training`/`ready`/`failed`), `created_at`. This is a separate entity from `jobs` — training a voice is its own flow, distinct from using one:

- **Training** a voice model is represented as an ordinary `job` (`capability: voice_model_training`) — it goes through the exact same submit/poll and credit hold→settle/release lifecycle as any other capability ([ADR 0002](0002-unified-async-job-model.md), [ADR 0003](0003-credit-ledger-hold-then-settle.md)); no new mechanism needed. The difference is only what success produces: instead of (or alongside) an `assets` row, it creates a `voice_models` row. This also means training gets the same no-charge-on-failure guarantee as everything else, for free.
- **Using** an existing voice model to generate speech is an ordinary TTS `job` ([ADR 0002](0002-unified-async-job-model.md)) that references a `voice_model_id` as part of its input, priced by the normal TTS rule (character count, [product-scope.md §2](../product-scope.md)). Reuse itself adds no extra cost beyond that per-call price — that's the point of it being an asset rather than a one-shot job.

A voice model's lifecycle is independent of generated media's: it is **not** subject to R2 asset retention ([ADR 0004](0004-asset-mirroring-r2-retention.md)) — that policy is about generated outputs (things a job produced), not a durable resource the user owns. A voice model persists until the user deletes it.

## Alternatives considered

- **One-shot voice cloning** (clone and immediately speak, don't retain the voice). Rejected: contradicts the explicit product intent — a cloned voice is meant to be a durable user asset, not a disposable byproduct.

## Consequences

**Positive:** matches the stated product intent; cleanly separates "assets a user owns and reuses" (`voice_models`) from "one-shot generation history" (`jobs`) — a distinction the schema needed regardless.

**Negative / open items:**
- Exact credit cost of *training* a voice (flat fee vs. based on sample length/count) isn't decided — a config detail, not architecture.
- Whether Azure/Google support an equivalent durable custom-voice concept (vs. only inline, per-call zero-shot cloning) is unconfirmed — checked when those adapters are actually built.
