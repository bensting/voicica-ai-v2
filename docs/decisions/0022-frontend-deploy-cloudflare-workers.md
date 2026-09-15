# ADR 0022: Frontend Deployed to Cloudflare Workers via OpenNext

- Status: Accepted
- Date: 2026-09-15

## Context

`voicica.ai`/`www.voicica.ai` are custom domains already bound (via the Cloudflare dashboard, not in any checked-in config) to a Worker named `voicica` — the prior project's own deployment (OpenNext + Cloudflare Workers, its `wrangler.jsonc` carried D1/Queues bindings this rewrite doesn't use). `frontend/web` had no deployment configuration of its own yet.

The immediate trigger is narrower than "ship the whole product live": a payment-gateway application needs a real, live business website showing verifiable contact information — specifically `/contact` (ADR 0019), drafted for exactly this. The backend isn't deployed anywhere public yet (still local-dev-only), so this pass deploys the marketing surface only; `(app)`/`(admin)` (both login-gated, both pure backend API consumers) won't function until the backend has a real URL and this is redeployed pointing at it. This is an accepted, explicit sequencing choice, not an oversight — none of the marketing pages this deploy is actually for (`/`, `/voice`, `/image`, `/video`, `/privacy`, `/terms`, `/contact`, `/get`) depend on the backend except the homepage's gallery strip, which already fails soft (empty state, not a crash) per its existing error handling.

**This doesn't reopen [ADR 0006](0006-database-orm-choice.md)'s rejection of Cloudflare Workers**, which was about running the backend's business logic (provider calls, DB queries, credit ledger) on Workers and found it too slow for this project's user-experience priority (`CLAUDE.md`, `product-scope.md` §0). Serving a Next.js frontend from Cloudflare's edge is a different workload entirely — mostly static/prerendered pages plus a handful of dynamic routes (`/get`'s server-side device check) — and is generally *fast* precisely because it runs at the edge, not despite it. The backend stays FastAPI, unaffected by this decision either way.

## Decision

**`@opennextjs/cloudflare`**, not the older `@cloudflare/next-on-pages` adapter — OpenNext is Cloudflare's own current recommendation for full Next.js framework support (App Router, Server Components, etc.) and is what the prior project already used successfully. Confirmed compatible with this app's exact Next.js version (16.3.4) before installing, not assumed.

**Same Worker name (`voicica`) as the prior project**, deployed from this repo instead. Workers are identified by name within an account; redeploying under the same name replaces that Worker's code in place, and the dashboard-configured custom domains carry over untouched — no DNS change, no new route configuration, `voicica.ai` starts serving the new app the moment this deploys. `wrangler.jsonc` here deliberately omits the prior project's D1/Queues bindings — this app doesn't have or need any Cloudflare bindings of its own (ADR 0005: a pure API consumer of the FastAPI backend).

**Image optimization disabled** (`images: { unoptimized: true }`) for this pass — Next's default optimizer needs a Node server or a Cloudflare-specific loader neither of which this deploy sets up yet; every image served today is a small local static asset (logo, Play Store badge) or already-compressed provider output, not worth the added complexity right now. Revisit if that changes (e.g. serving large photos directly from R2 through `next/image`).

**Build-time env values live in a committed `.env.production`** — every value in it is a `NEXT_PUBLIC_*` one already documented as meant to be public (`.env.local.example`'s own comment on the Firebase key), so there's no secret being checked in. `NEXT_PUBLIC_API_BASE_URL` is set to `https://api.voicica.ai`, an **unconfirmed guess** at the eventual backend URL (mirroring the prior project's own `vp.voicica.ai` subdomain convention) — not a real, reachable address yet. This needs a real value and a redeploy once the backend actually has one; called out explicitly in the file itself so it isn't forgotten.

**Verified locally on the real Workers runtime before touching the live domain**: `opennextjs-cloudflare build` + `opennextjs-cloudflare preview` (runs the actual built Worker under `wrangler dev`, not just Next's own dev server) — confirmed `/`, `/contact` (real operator name/address/email present), `/get`, `/privacy` all return 200, `/get`'s server-side Android/desktop CTA branching still works correctly, and `/robots.txt`/`/sitemap.xml` correctly resolve to the real `voicica.ai` domain from the production env values.

## Alternatives considered

- **Cloudflare Pages with `@cloudflare/next-on-pages`.** Rejected — Cloudflare's own guidance now points to OpenNext for full framework support; `next-on-pages` has had rougher edges with newer App Router features historically, and there was no reason to risk that when the prior project already proved OpenNext works for this exact app shape.
- **Deploy the whole product now, backend included.** Rejected for this pass — the actual trigger (payment-gateway application needing a live site) only needs the marketing surface; standing up a real backend deployment is a separate, bigger task not blocking this one.
- **A new Worker/subdomain first, cut over the domain once confirmed.** Considered, not needed — same-name redeploy was confirmed to carry the dashboard-configured custom domains automatically, and the local Workers-runtime preview already gave real confidence before touching the live domain, so an intermediate staging step didn't add much here.

## Consequences

**Positive:** a real, live website now exists at `voicica.ai` for the payment-gateway application, deployed to the same Worker/domain the prior project already had configured — no DNS/domain rework needed. The deploy pipeline (`npm run deploy`) is reusable for every future frontend change, marketing or otherwise.

**Negative / open items:**
- `(app)`/`(admin)` will not work on the live domain until the backend is deployed somewhere public and `NEXT_PUBLIC_API_BASE_URL` is updated to the real address (currently an unconfirmed guess) — a known, accepted gap for this pass, not a bug.
- Image optimization is off entirely; fine for today's small local assets, needs a real decision (Cloudflare Images, a custom loader, or re-enabling with the Workers-compatible path) if this app starts serving large remote images through `next/image`.
- No CI/CD — `npm run deploy` is run by hand from a developer machine for now. Fine at this stage (one deploy so far); revisit once deploys are frequent enough that this becomes friction.
