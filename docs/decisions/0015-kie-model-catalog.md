# ADR 0015: Kie Model Catalog — Hand-Curated Config, Not Code

- Status: Accepted
- Date: 2026-09-12

## Context

[product-scope.md §1.1](../product-scope.md) already decided Kie is a "wholesale" gateway — `providers/kie.py` should be a generic `run(model_id, inputs)` executor, with which `model_id`s exist and what each expects treated as configuration, not new adapter code per model. That was a direction, not yet a concrete shape: nothing had actually verified *how* heterogeneous Kie's real models are, or designed the data structure "config" means in practice.

Verified directly against Kie's real site this round (`docs.kie.ai` exposes no programmatic model-list/schema/pricing endpoint — only human-browsable Market/Pricing/Playground pages, confirmed by inspecting its nav), using two real model families as concrete evidence:

- **The wire protocol is already generic.** Every model, regardless of vendor, submits through the same endpoint: `POST /api/v1/jobs/createTask`, body `{"model": "<opaque string>", "callBackUrl": "...", "input": {<opaque object>}}` → `{"data": {"taskId": "..."}}`. `model` is never parsed or reconstructed by this codebase — stored and sent back verbatim.
- **Two real examples, `flux-2/pro-text-to-image` and `gpt-image-2-5-flare-text-to-image`**, both price by a `resolution` field (1K/2K/4K) and leave other fields (`aspect_ratio`, `background`) free — confirming a single "which field decides the price tier" pricing rule is enough for this category, not a full parameter-combination price table.
- **A genuine cross-field constraint exists**: `gpt-image-2-5-flare-text-to-image` restricts certain `aspect_ratio` values to `resolution=1K` only. This isn't modeled up front (see Consequences) — Kie's own `createTask` call rejects an invalid combination, which surfaces as an ordinary failed job (no charge, ADR 0003), not a data-integrity problem.
- **Kie's own reported cost per task (`creditsConsumed`)** is confirmed present on `GET /api/v1/jobs/recordInfo` (architecture.md §3d) — this curated catalog's pricing numbers are only ever used for the *estimate* at hold time; settlement always uses Kie's own number (see Decision).

## Decision

**Two new tables, not an `app_settings` JSON blob.** [data-model.md](../data-model.md)'s existing config-classification rule already called Kie's catalog "structural/engineering config... starts as a file, becomes DB-backed once admin needs to edit it without a redeploy" — this catalog hits that trigger immediately (the whole point raised when designing this was adding a model via data only, no redeploy), so it goes straight to DB-backed, skipping the file stage. Real tables rather than a JSON blob under one `app_settings` key (unlike `capability_menu`, ADR 0012) because this data grows by *row* over time the way `voice_catalog` does, not as one small, rarely-changed structure:

```
kie_categories
  id            e.g. "text-to-image" — primary key, hand-picked slug
  display_name  e.g. "Text to Image"
  output_type   "image" | "video" | "audio" — selects which frontend result-renderer a category's jobs use
  enabled

kie_models
  model_id       Kie's own real string, e.g. "flux-2/pro-text-to-image" — primary key, stored verbatim, never parsed
  category_id    FK -> kie_categories.id
  display_name   e.g. "Flux-2 — Pro"
  input_schema   jsonb: [{name, label, type: select|text|number|image|boolean, options?, default, required}]
  pricing        jsonb: {"param": "resolution", "costs": {"1K": 5, "2K": 7}} or {"flat": N}
  enabled
```

**`providers/kie.py` needs zero per-model code.** `submit()` takes `model_id` + an `input` dict and calls the one real endpoint above; `poll()` calls the one real `recordInfo` endpoint (architecture.md §3d's state mapping). Neither method branches on which model it's given — the catalog tables are the only place a new model exists.

**Adding a model within an existing, already-built category is a pure data change** (a `kie_models` row) — no backend or frontend code. **Adding a new category is data-only for its input side** (the generic schema-driven form already renders whatever `input_schema` a new model declares) but needs a one-time frontend addition *only if* its `output_type` is genuinely new (no image/video/audio renderer exists yet) — a category reusing an already-supported `output_type` is data-only end to end, same as a same-category model.

**Cross-field constraints (e.g. GPT Image 2.5's aspect-ratio-limits-resolution rule) are not modeled in `input_schema` for v1.** Encoding every vendor's per-model validation quirk generically would make the schema format itself the bottleneck this ADR exists to avoid. Kie's own `createTask` call already enforces its own constraints — an invalid combination a user managed to submit becomes an ordinary failed job, refunded like any other failure (ADR 0003), not a broken one. Revisit only if this actually causes a meaningful rate of real user-facing failures once traffic exists.

**Settlement: Kie's `creditsConsumed` *is* this catalog's own credit unit, 1:1 — no exchange-rate/margin layer.** The curated `pricing.costs` numbers are copied directly from Kie's own displayed pricing (e.g. `{"1K": 5, "2K": 7}` are Kie's real credit counts), so `estimated_cost` and Kie's own `creditsConsumed` already speak the same unit by construction. `actual_cost = creditsConsumed` directly at settlement (ADR 0003's hold→settle, using Kie's authoritative number instead of re-deriving one); `estimated_cost` is the fallback only if Kie ever omits it. A markup/margin on top of Kie's own pricing is a future business decision (real revenue economics), not a data-modeling one — not built here, and this catalog's numbers should not be read as our final consumer-facing prices once one exists.

**Kie completion is finalized from exactly one code path, called two ways** — `services/jobs.finalize_kie_job()`, given a job id and a `JobStatus`. The webhook (`POST /webhooks/kie`, primary path per architecture.md §3d) re-polls `recordInfo` itself rather than trusting the callback body's own payload — one source of truth for "what does a terminal Kie job look like," at the cost of one extra HTTP call per webhook delivery, not a concern at this scale. The poll-based cron sweep (`worker/cron.py`, fallback path, every 1 minute for jobs still `processing`) calls the same function. Both paths lock the job's `CreditHold` row (`SELECT ... FOR UPDATE`) before checking `status == "active"`, so a webhook and a sweep tick landing on the same job at the same moment can't double-settle credits — the second to arrive blocks on the row lock, then finds the hold already resolved and no-ops.

## Alternatives considered

- **Auto-discover the catalog from a Kie API.** Not possible — verified no such endpoint exists (see Context). Not a design choice; a hard fact this round's research closed out.
- **One shared parameter-combination price table (every field × every value).** Rejected: both real examples price off exactly one field; a full combinatorial table is unused complexity for data this shape. Revisit if a future Kie model genuinely needs it.
- **Keep the catalog in `app_settings` like `capability_menu`.** Rejected: that pattern fits one small, holistically-edited structure; this one is many independently-added rows, closer to `voice_catalog`'s shape.

## Consequences

**Positive:**
- Flux-2 and GPT Image 2.5 (this ADR's first real entries) prove the shape against two independently-priced real vendors' models, not a hypothetical.
- A new model in an existing category — the common case as the catalog grows — really is zero-code, verified against Kie's actual wire protocol rather than assumed.

**Negative / open items:**
- No cross-field constraint validation (see Decision) — an invalid combination fails at Kie, not before. Acceptable at current scale; revisit if it becomes a real UX problem.
- `input_schema`'s field-type vocabulary (`select|text|number|image|boolean`) is a starting guess sized to the two models this ADR actually built against — a genuinely new input shape (e.g. a multi-image reference upload) may need a new type added later.
- No markup/margin layer on Kie's pricing yet (see Decision) — today's numbers are Kie's own, not a real consumer price.
- Per-model `max_jobs`/rate limits for `queue:kie-submit` (ADR 0014) are provisional, unmeasured, same caveat as Azure/Google's queues.

## Related

- Implements the catalog [product-scope.md §1.1](../product-scope.md) already called for, and the "submit"/"track" split [ADR 0014](0014-background-job-execution.md) already designed (`queue:kie-submit`, webhook + cron sweep).
- Resolves [ADR 0003](0003-credit-ledger-hold-then-settle.md)'s open item on Kie's `actual_cost` divergence — settled directly from `creditsConsumed`, 1:1 (see Decision).
