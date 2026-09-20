# ADR 0027: Generated Assets Served Directly From R2's Public Domain, With a Database-Driven Retention Window

- Status: Accepted
- Date: 2026-09-20

## Context

Since [ADR 0004](0004-asset-mirroring-r2-retention.md), every generated file (audio, image, video) is mirrored into R2, but never served from there: `GET /jobs/{id}/asset` read the whole object into the API process's memory and returned it, and the frontend fetched it with an auth header, converted it to a `blob:` URL, and only then showed it. That was a deliberate workaround — R2 presigned GET URLs were rejected by this environment's botocore ("Missing x-amz-content-sha256"), so the proxy was "the fallback that's actually verified working" (its own docstring said to revisit).

It doesn't scale, and it's already a product problem before scale:

- **Latency**: a video had to be fully downloaded before it could start playing; no Range requests, so no seeking; every thumbnail in Explore/history was a full-size original fetched through the API.
- **Load**: every byte crossed R2 → the Render instance → the browser, held fully in memory per request, competing with generation traffic for the same small instance. Streaming the response would only soften the memory problem, not the bandwidth or the missing cache.
- **No caching**: a public creation viewed by 100 people was read from R2 100 times through the API.

The project's stated priority is end-user experience over infrastructure convenience ([ADR 0006](0006-database-orm-choice.md)), and this is a direct instance of it.

## Decision

**All generated assets are served straight from R2's public domain; the API no longer proxies any media bytes.**

- The bucket is exposed on a public domain — `assets.voicica.ai` in production (Cloudflare custom domain on the `voicica-v2` bucket), the bucket's own `pub-<hash>.r2.dev` URL in local dev — configured by the existing `R2_PUBLIC_BASE_URL`. (It was already required for Kie image-to-image reference uploads, [ADR 0016](0016-kie-image-to-image-uploads.md); it is now required in every environment.)
- **Access control becomes "unguessable URL", not "authenticated fetch".** Object keys are `jobs/{job_id}.{ext}` where `job_id` is a random UUIDv4 (122 bits), the bucket does not allow listing, and a private job's id is never returned to anyone but its owner. `visibility` ([ADR 0010](0010-public-gallery-visibility-flag.md)) therefore now means only "listed in the public gallery"; it no longer means "nobody else can open the file". This is the standard capability-URL model used by comparable generation products.
- `jobs.output` stores only the object key (`asset_key`). The client-facing `asset_url` is derived at response time from `R2_PUBLIC_BASE_URL` (`schemas.py`), so moving the bucket behind a different domain never strands stored rows. Migration `0014` rewrote existing rows from the old `/jobs/{id}/asset` path to the key.
- `GET /jobs/{id}/asset` and `assets.download_bytes()` are deleted. The frontend uses plain `<img src>` / `<video src>` / `<audio src>` pointing at the URL (browser-native lazy loading, caching, Range/seek), and its blob-fetch helper is gone. Objects are uploaded with `Cache-Control: public, max-age=604800` (keys are immutable; capped at a week so an expired file doesn't linger in edge caches for a year).
- Download is a `fetch()` of the URL saved through a blob (a cross-origin `<a download>` is ignored by browsers), which needs a **CORS rule on the bucket** allowing `GET`/`HEAD` from the site's origins. If the fetch fails it falls back to opening the URL in a new tab. `cache: "reload"` is used because an earlier `<img>` load (no `Origin` header) can leave a cached copy without CORS headers.

**Retention is a database setting, enforced by our own sweep — not by an R2 lifecycle rule.**

- New `app_settings` key `asset_retention_days` (default 90; changeable from the admin settings endpoint without a deploy, [ADR 0012](0012-app-settings-table.md)).
- The value is stamped into each asset's own `assets.expires_at` **at creation time**, so changing the setting only affects files generated afterwards: shortening it never silently deletes existing work, and lengthening it cannot resurrect files already gone.
- `worker/cron.py sweep_expired_assets` (hourly, a timer loop inside `dispatcher.py` like the other sweeps) deletes the R2 object of every asset past `expires_at`, marks it `mirror_status = "expired"`, and rewrites the job's stored `output` to `{asset_key: null, asset_expired: true}` (the API then returns `asset_url: null, asset_expired: true`). A failed R2 delete leaves the row untouched and is retried next tick. The database is the single source of truth; a lifecycle rule can't read our settings, so if one is configured at all it must be a *wider* backstop (e.g. 180 days on the `jobs/` prefix) for orphans only.
- `GET /jobs` (history) only returns jobs inside the retention window; the gallery already required `mirror_status = "done"`, so expired items drop out of Explore automatically. History shows "Expired" on the rare row where the sweep has run but the job is still in the window.

## Alternatives considered

- **Keep the proxy, but stream it and add `Cache-Control`/Range support.** Fixes memory and video start-up, but every byte still flows through the Render instance, there is still no shared cache across users, and it remains the thing that falls over first as traffic grows. A cheaper stopgap, not a solution.
- **Public URLs only for `visibility = public` jobs, private ones through short-lived signed URLs.** The "correct" access-control answer, but it needs the presigning problem solved (or a Worker validating short-lived tokens), a copy-or-move step whenever visibility flips, and two code paths for every media element. Rejected as premature for a personal-scale product where everything is user-generated content behind long random ids; revisit if content that must be genuinely revocable is ever added.
- **A hard-coded 90 days.** Simpler, but retention is exactly the kind of number that needs tuning after real usage, and the setting costs almost nothing given `app_settings` and `assets.expires_at` already existed.
- **An R2 lifecycle rule as the primary mechanism.** Can't read the database setting, so the UI and the actual deletion could disagree in the worst direction (link shown, file already gone). Kept only as a possible wide backstop.

## Consequences

**Positive:** media loads at CDN speed with native streaming and seeking; the API instance no longer carries media bytes or memory for them; a public creation is fetched from R2 once per edge cache rather than once per viewer; the frontend is simpler (no blob/observer plumbing); expiry is enforced deterministically with the UI kept in sync. Since assets are now genuinely public-URL, the marketing homepage's "Made with Voicica" strip can show real thumbnails later ([ADR 0019](0019-marketing-site-scope-and-i18n.md)'s deliberate text-only limit was an auth-boundary concern that no longer exists) — not built here.

**Negative / open items:**
- **A private creation's link is shareable and unrevocable** (until it expires or is deleted). The privacy policy copy was rewritten to say exactly this rather than "visible only to you".
- Deleting a single job/asset on request isn't implemented (no delete-a-creation feature exists yet); when it does, it must delete the R2 object too.
- CDN edge caches can serve an already-deleted file for up to the `max-age` (7 days).
- Rollout ordering: the backend (migration `0014`, new `asset_url` shape) and the frontend (which now uses that URL directly) must both be deployed; between the two, one side is briefly out of step (acceptable pre-launch — deploy the backend, then immediately the frontend).
- `assets.expires_at` has no index; the hourly sweep is a scan of a small table today. Add a partial index (`WHERE mirror_status = 'done'`) if that table ever grows large.
- Test files written to the production bucket before the R2 split ([ADR 0025](0025-separate-test-database.md) follow-up) remain there as orphans until the wide backstop rule or a manual cleanup removes them.
