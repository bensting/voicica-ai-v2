# ADR 0016: Kie Image-to-Image — Short-Lived Public Uploads

- Status: Accepted
- Date: 2026-09-12

## Context

Extending the Kie catalog ([ADR 0015](0015-kie-model-catalog.md)) to image-to-image models (Flux-2 Pro/Flex, GPT Image 2.5 Flare/Sunburst, each already offering an image-to-image `model_id` alongside their text-to-image one) surfaces a real constraint verified against both vendors' actual `createTask` request shapes: the reference-image parameter (`input_urls` on every model checked — a naming convention that happens to already agree across both Flux-2 and GPT Image 2.5) is an array of **URLs Kie's own servers fetch themselves**, not an uploaded file and not base64 — confirmed from a real request body on both vendors' "API" tabs.

This doesn't fit this codebase's existing asset story. `services/assets.py`'s own docstring is explicit about why: R2 objects are served through this backend's own authenticated proxy (`GET /jobs/{id}/asset`), not a public URL — presigned R2 GET URLs reject in this environment ("Missing x-amz-content-sha256"), and nothing about this app's outputs needed a public URL before now. Kie's server has no way to attach this app's Firebase auth header, so it categorically cannot fetch through that proxy — an image-to-image reference genuinely needs a real, unauthenticated, publicly fetchable URL to exist, however briefly, for Kie to read.

## Decision

**A reference image is uploaded to a distinct R2 prefix (`uploads/`, separate from generated outputs' `jobs/`) fronted by `R2_PUBLIC_BASE_URL`** (`core/config.py`'s already-reserved-but-previously-unused field — a Cloudflare R2 bucket's own public `pub-<hash>.r2.dev` development URL is enough, no custom domain required) — `services/assets.py`'s new `upload_public_bytes()`. `POST /kie/uploads` (multipart, auth required) is the one new endpoint: it uploads the file and returns `{url, r2_key}`; the frontend then places `url` into the Kie model's `input_urls` field before calling `POST /generate/kie` as normal.

**The upload is deleted the moment its job reaches any terminal outcome — success, failure, or a failure to even enqueue** — not kept for the generated-output retention window ([ADR 0004](0004-asset-mirroring-r2-retention.md)'s 90 days). A user's own uploaded photo being world-fetchable-if-the-URL-leaks is a real, if narrow, exposure; there is no reason to hold it open past the single Kie call that needed it. This mirrors an already-established position in this codebase: voice cloning ([ADR 0009](0009-voice-cloning-reusable-asset.md)) never stores a user's training sample at all, for the same reason (minimize how long sensitive input data outlives its one legitimate use). `services/jobs.py` tracks each upload's `r2_key` on the `Job` row (`input.uploaded_r2_keys`, alongside `inputs` itself) and a small `_cleanup_kie_uploads()` helper is called at every terminal transition for a Kie job (`_enqueue_or_fail`'s failure branch, `execute_kie_submit_job`'s failure branch, `finalize_kie_job`'s success and failure branches) — best-effort, logged on failure, never blocking the job's own outcome (same posture as Fish Audio's best-effort voice-model delete).

**`input_schema`'s field-type vocabulary gains a real `image` type now** (declared but unrendered as of ADR 0015): `{name, label, type: "image", multiple: bool, max?: int, required}`. The frontend calls `POST /kie/uploads` once per selected file as soon as it's picked (not deferred to submission time), collecting the resulting URLs into that field's value — so by the time "Generate" is pressed, `inputs[field.name]` already holds real URLs, and `submit_kie_job` just needs the accompanying `r2_key`s to track for cleanup.

## Alternatives considered

- **Embed the image as base64 in `input`.** Not viable — verified against a real request body from both vendors: the field is named and shaped as a URL array, not inline data. Not a design choice.
- **Ask Kie for a presigned upload endpoint of its own.** No such endpoint is documented (consistent with this project's earlier finding, ADR 0015, that Kie's API surface is minimal — createTask/recordInfo only).
- **Keep the upload public for the same 90-day window as generated outputs.** Rejected: simpler (no cleanup code) but keeps sensitive user-uploaded input material world-fetchable far longer than the single call that ever needed it, for no benefit — outputs are kept because a user might want to revisit them; an input photo already served its purpose the moment the job finished.

## Consequences

**Positive:**
- Unblocks image-to-image for both vendors already in the catalog, using the same field name (`input_urls`) and upload mechanism for each — no per-vendor special-casing.
- The short-lived-public-then-deleted pattern is reusable for any future capability with the same "vendor fetches from a URL" shape, not a one-off hack.

**Negative / open items:**
- A genuinely adversarial actor who captures the URL in the few seconds/minutes it's live could fetch the image before cleanup runs — accepted as a narrow, time-boxed exposure, not eliminated (eliminating it entirely would mean Kie can't reach the image at all, defeating the feature).
- Cleanup is best-effort or a crashed worker process, an enqueue path that never reaches a terminal state some other way, etc. could leave an orphaned upload — no dedicated sweep for stray `uploads/` objects exists yet; revisit if this proves to happen in practice (a simple time-based bucket lifecycle rule on the `uploads/` prefix, independent of application code, is the likely fallback rather than another cron job).
- `R2_PUBLIC_BASE_URL` must actually be configured (a real bucket setting change, external to this codebase) before any image-to-image model can be enabled — tracked as a setup dependency, not a code gap.

## Related

- Extends [ADR 0015](0015-kie-model-catalog.md)'s catalog (`input_schema`'s `image` type, previously declared but unrendered) rather than replacing anything in it.
- Echoes [ADR 0009](0009-voice-cloning-reusable-asset.md)'s "don't keep sensitive input material longer than its one use" position, applied to a different resource shape (a public URL's exposure window, not a stored file).
