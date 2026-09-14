# ADR 0017: Video Category, Per-Unit Pricing, and Catalog Rows That Outnumber Real Kie Models

- Status: Accepted
- Date: 2026-09-12

## Context

Extending the Kie catalog ([ADR 0015](0015-kie-model-catalog.md)) to video surfaced two things neither prior ADR anticipated, both confirmed against real vendor data rather than assumed:

**Video pricing isn't one shape.** Grok Imagine Video 1.5 (`grok-imagine-video-1-5-preview`, real schema confirmed via Kie's own "expected fields" panel) prices **per second**: 2.4 credits/sec at 480p, 4.5 at 720p, with `duration` a genuine continuous field (`number`, range `[1, 15]`, default `8`). Veo 3.1 (`veo-3-1`) prices as a **flat amount per generated video**, varying by two independent input choices at once — a quality tier (Lite/Fast/Quality) *and* resolution (720p/1080p/4K) — not a rate times a duration the caller controls. Neither of ADR 0015's two pricing shapes (`flat`, or one field looked up in a `costs` table) covers a per-unit rate; a third shape is needed.

**One real Kie model can bundle several logically distinct offerings behind an input field, not a model string.** Verified two ways: reading Veo 3.1's Playground (a "Model" field offering Lite/Fast/Quality inside the same form) and then with a real `createTask` call — omitting that field entirely still succeeded, and `recordInfo` echoed back `"model":"veo3_fast"` *inside* `input`, alongside a top-level `"model":"veo-3-1"` that never changed. So `provider_model_id` (what's actually sent to Kie) is `"veo-3-1"` for all three tiers; the tier itself is an ordinary input field Kie happens to call `model`, confusingly enough to be worth a real ADR note.

## Decision

**Split Lite/Fast/Quality into three separate catalog rows anyway, matching how Flux-2 Pro/Flex and GPT Image 2.5 Flare/Sunburst are already modeled.** This was a real product question, not just a technical one — the alternative (one catalog row, a quality-tier field inside the generation form) would make picking a quality tier work differently depending on which vendor happened to expose it as a separate model string versus an input field, which is exactly the kind of inconsistency a catalog is supposed to hide. Every quality/tier choice a user makes now happens the same way everywhere: pick a row in the model list. This also happens to simplify pricing back down to ADR 0015's existing single-field lookup shape *per row* (`{"param": "resolution", "costs": {...}}`) — the two-parameter table is never actually needed as long as splitting stays the norm whenever a vendor exposes tiers this way.

**`kie_models` gains two columns to make this possible**: `provider_model_id` (the literal string sent to Kie's `createTask`, may repeat across rows — Veo's three tiers all have `provider_model_id="veo-3-1"`) and `fixed_inputs` (extra `input` fields this row pins for every submission, e.g. `{"model": "veo3_fast"}` — never listed in `input_schema`, never user-editable, merged in at submission time by `services/jobs.py submit_kie_job` before the job's `input` is even persisted). `model_id` (the primary key) becomes purely *our own* catalog identifier — used for routing/display/`Job.model_id`, decoupled from whatever Kie itself calls the model. For every row catalogued before this ADR, `provider_model_id` simply equals `model_id` and `fixed_inputs` is empty — no behavior change for them.

**A third pricing shape for a genuine rate**: `{"rate_param": "duration", "tier_param": "resolution", "rates": {"480p": 2.4, "720p": 4.5}}` — `credits = ceil(rates[inputs[tier_param]] * inputs[rate_param])`. `ceil` because credits are integers (docs/data-model.md's conventions) and a real rate × duration is often fractional (a real "19.2 credits" Run price was observed live on Kie's own site).

**A new category, `image-to-video`, with `output_type: "video"`** — the first time this matters: the generation page's result renderer, previously only ever rendering `<img>`, needs a real `<video>` branch. `KieModelResponse` now also carries `output_type` (denormalized from its category) so the frontend doesn't need a second fetch to know which renderer to use.

**Scope for this pass**: `grok-imagine-video-1-5-preview` (the model actually seeing real usage, per direct product judgment — the sibling `grok-imagine` family's own `image-to-video` mode was considered and set aside, not because it's worse, but because this is the one people actually reach for) and `veo-3-1`'s **Lite tier only**. Fast and Quality tiers are catalogued as straightforward follow-on rows once Lite is verified live — same `provider_model_id`, different `fixed_inputs`/`pricing`, no new mechanism needed.

**Correction, same day**: the first version of Veo Lite's `input_schema` (separate `start_frame`/`end_frame` fields, `aspect_ratio` lower-case, no `duration`) was built from the Playground's UI shape and a naming-pattern guess, not Kie's actual published API contract — and turned out wrong on several points at once when checked against `docs.kie.ai`'s real `createTask` body-params reference for `veo-3-1`. Two lessons worth keeping:
- **Kie's own account dashboard (`kie.ai/logs`) shows request bodies in an internal camelCase shape** (`imageUrls`, `aspectRatio`, `generationType`, `waterMark`) that is *not* the wire format `POST /api/v1/jobs/createTask` actually expects — that's `image_urls`, `aspect_ratio`, `generation_type`, `watermark` (snake_case), per the published param reference. Trusting the dashboard's display format over the docs is what produced the wrong first schema; the published body-params reference is the one source of truth for field names, confirmed by then running a real submission through our own `submit_kie_job` (not Kie's own website) with the corrected names and getting a real success.
- **Start/end frame isn't two fields — it's one array, `image_urls`, holding 1 or 2 images** (1 = single reference frame the video unfolds around; 2 = first frame + last frame). `generation_type` (enum: `TEXT_2_VIDEO` / `FIRST_AND_LAST_FRAMES_2_VIDEO` / `REFERENCE_2_VIDEO`) is left **unset** in `input_schema` entirely — Kie's docs state it's auto-derived from whether `image_urls` is present, which conveniently sidesteps a real gap in `fixed_inputs`: that mechanism only holds static per-row values, not a value that depends on *another input field being filled in or not*. `enable_fallback` is documented deprecated and left out. `duration` **is** a real, confirmed field after all (enum `4`/`6`/`8`, default `8`, doesn't affect Veo's flat per-video price) — the "leave unconfirmed fields out" caution from the first pass was the right instinct given what was known then, but the field turned out fully documented once the real reference was checked instead of inferred.

Corrected schema verified for real through `submit_kie_job` end-to-end: `estimated_cost` (30, Lite/720p) matched Kie's own `creditsConsumed` exactly, same as Grok's per-second shape did.

**A second, smaller correction, caught by review right after the above shipped**: describing a numeric range in `note` text isn't the same as enforcing it. Veo's `duration` (a closed `4`/`6`/`8` enum) had gone in as free-text `type: "number"` — nothing stopped a user typing `5` or `100`. Fixed with a `numeric: true` flag on `KieInputField` (`select` sends a real number instead of the option's string) so it renders as three quick-pick pills, same as `aspect_ratio`. Grok's own `duration` (a genuine `[1, 15]` range, so a `select` doesn't fit) had the identical gap in its own `number` field — fixed with a new `slider` field type instead of a tighter clamp, matching Kie's own dashboard UI for this exact field: a range input's displayed value is read-only, so an out-of-range value isn't just discouraged, it's not producible at all.

## Alternatives considered

- **One row per real Kie model, tier selection as an ordinary input field.** Rejected — see Decision: makes the same product concept (picking a quality tier) behave differently per vendor depending on an implementation detail of that vendor's own API, which is precisely what the catalog abstraction exists to prevent.
- **A single generic "multi-key lookup" pricing shape** (params: [...], costs: {"key1|key2": N}) to cover Veo without splitting rows. Not built — splitting rows already covers every real case gathered so far with the simpler single-key shape; a composite-key shape stays a documented option for whenever a future model needs a real 2D price this ADR's splitting rule can't collapse away, rather than something built speculatively now.

## Consequences

**Positive:**
- Video's real per-second pricing (Grok) and Veo's tier-as-a-field quirk are both handled with additive, narrow changes — no rework of ADR 0015's existing rows or code paths.
- `provider_model_id`/`fixed_inputs` is a generically reusable escape hatch for the next vendor that also bundles variants behind a field instead of a model string, not a Veo-specific hack.

**Negative / open items:**
- Veo Lite is now fully verified (`fixed_inputs={"model":"veo3_lite"}` confirmed via Kie's own request log for a real, successful, 30-credit job) and enabled. Quality's `fixed_inputs` value (`"veo3_quality"`, by the same confirmed naming pattern as `veo3_fast`/`veo3_lite`) is still an inference, not independently confirmed — verify with one real call before cataloguing/enabling it, same discipline as everything else here.
- The composite-key pricing shape this ADR chose not to build stays a real gap if a future model's price genuinely can't be collapsed into separate rows (e.g. too many independent dimensions to reasonably split).

## Related

- Extends [ADR 0015](0015-kie-model-catalog.md) (catalog shape) and [ADR 0016](0016-kie-image-to-image-uploads.md) (the `image` field type, reused here for Veo's `image_urls` field — `multiple: true, max: 2`, the same mechanism Grok's `image_urls` already uses at `max: 7`, no new frontend code needed).
