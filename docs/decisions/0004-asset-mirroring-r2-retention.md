# ADR 0004: Mirror Generated Assets into Cloudflare R2 with a Retention Window

- Status: Accepted
- Date: 2026-09-11

## Context

Kie's result URLs expire roughly 24 hours after generation ([architecture.md §3d](../architecture.md)). The product includes a history view ([product-scope.md §3](../product-scope.md)) where users expect to revisit past generations well beyond that window. Keeping every asset forever is the simplest UX but has unbounded, ever-growing storage cost — especially for video. Not persisting at all makes the history feature broken for anything older than a day.

## Decision

On every job that reaches `succeeded`, asynchronously download the result from the provider's (temporary) URL and upload it into **Cloudflare R2** (S3-compatible object storage, no egress fees — a good fit since these assets get served to the same user repeatedly). This mirroring step runs *after* the job's own terminal state and is tracked independently (`mirror_status: pending / done / failed`) so it can retry without re-running the generation itself.

Mirrored assets are kept for a **configurable retention window** — a config value (default TBD, e.g. 90 days as a starting point; can vary per capability since video storage costs more than audio/image), not a number baked into the architecture. R2's own lifecycle rules perform the actual deletion once an object passes its window. Our own job/asset record independently stores the computed expiry timestamp (`mirrored_at + retention_days`), so the API/frontend can deterministically show "expired" without probing R2 for existence.

## Alternatives considered

- **Persist forever.** Rejected: storage cost grows without bound and without a corresponding product reason to keep everything indefinitely.
- **Don't persist — keep only the provider's ephemeral URL.** Rejected: history breaks after ~24h, which defeats the purpose of having a history feature at all.
- **Persist only on explicit user action (a "save" button).** Rejected: most users won't think to click save inside the 24h window for something they'd only later realize they wanted — it makes the *default* experience the broken one.

## Consequences

**Positive:**
- History reliably works within the retention window, for every job, with no user action required.
- Storage cost is bounded and tunable purely via config (retention days), no architecture change needed to adjust it.
- R2's lifecycle rules handle deletion; no custom cleanup cron is needed for that part.

**Negative / trade-offs:**
- Mirroring is an extra async step that can itself fail (network issue, or the retry loses the race against Kie's 24h window) — needs its own retry/backoff and an alerting path for the rare case an asset is lost entirely before it could be mirrored.
- Adds Cloudflare R2 as an infrastructure dependency, independent of wherever the backend itself ends up hosted.
- A finite retention window means old history entries eventually disappear — needs to be visible to the user in the history UI (e.g., an "expires in N days" indicator), not a silent surprise.

## Open items

- Exact retention period(s) per capability — config to set when each capability is implemented, not decided here.
- Whether the frontend shows any warning as an asset nears expiry.
- R2 bucket/credentials live in `core/config.py`, per the existing pattern for provider keys.
