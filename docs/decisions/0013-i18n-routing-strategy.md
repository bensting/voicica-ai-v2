# ADR 0013: i18n Routing Strategy — Locale-Prefixed URLs for Marketing, Cookie for the App

- Status: Accepted
- Date: 2026-09-11

## Context

Target market is Thai, Indonesian, and Spanish speakers ([`product-scope.md` §0](../product-scope.md)), not the prior project's en/zh-CN/zh-TW — so the frontend needs a real locale-switching mechanism, not just new language files. Two candidate mechanisms exist, and they pull in opposite directions:

- **Locale-prefixed URLs** (`/th/...`, `/es/...`): each language gets its own crawlable, `hreflang`-linkable URL — the standard pattern for public, SEO-relevant pages (Google's own guidance, and the pattern `next-intl`/Next.js's App Router i18n examples are built around).
- **Cookie/localStorage-stored locale, no URL prefix**: simpler routing, no `[locale]` segment or middleware redirect — the pattern most logged-in SaaS dashboards use (Notion, Slack), since authenticated pages aren't crawled and don't need per-language URLs.

`frontend/web` already has exactly the structural split ([ADR 0005](0005-frontend-surfaces.md)) this question maps onto: `(marketing)` (not built yet, public, meant to be crawled — [ADR 0011](0011-frontend-framework.md) picked Next.js partly *for* its SSR/SEO fit here) and `(app)` (authenticated, the current TTS slice, never crawled).

## Decision

Split by surface, not one mechanism for the whole site:

- **`(marketing)`**: locale-prefixed URLs (`/th/...`, `/id/...`, `/es/...`; `en` TBD whether it gets its own prefix or is the unprefixed default — a detail to settle when `(marketing)` is actually built, not blocking this ADR).
- **`(app)`**: a plain cookie (no URL prefix) holding the active locale, read by `lib/api.ts` calls like `GET /config/menu?locale=` ([`api-contract.md`](../api-contract.md)). Signed-in users could later get this synced to a `users` column for cross-device consistency — not needed for the current single-surface slice.

The language switcher itself lives in the still-unbuilt top-left drawer (agreed position, not yet implemented) — this ADR settles the storage/routing mechanism it will write to, not the UI.

## Alternatives considered

- **Locale-prefixed URLs everywhere, including `(app)`.** Rejected: authenticated pages are never crawled, so the SEO benefit that justifies the extra routing complexity doesn't apply there — it would just be `[locale]`-segment overhead for no payoff.
- **Cookie-only everywhere, including `(marketing)`.** Rejected: defeats the reason `(marketing)` exists as SSR'd, crawlable pages in the first place — a search engine can't discover or rank content it can't reach at a stable, language-specific URL.

## Consequences

**Positive:** unblocks two things that were waiting on this: wiring `next-intl` (or equivalent) for `(marketing)` once it's built, and removing `lib/api.ts`'s `getMenu()` hardcoded `locale="en"` for `(app)` (now reads the cookie via `lib/locale.ts`, default `"en"` until the drawer writes to it).

**Negative / open items:** `en`'s exact URL shape for `(marketing)` (prefixed or default-unprefixed) is still open, decide when that surface is actually built. The `(app)` cookie has no cross-device sync yet (see above) — fine for now, single-surface.
