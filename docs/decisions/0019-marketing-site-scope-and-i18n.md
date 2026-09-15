# ADR 0019: Marketing Site — Page Scope, Content Strategy, and i18n Registration

- Status: Accepted
- Date: 2026-09-14

## Context

`(marketing)` ([ADR 0005](0005-frontend-surfaces.md)) has been an empty route group since the project started — `product-scope.md` §3 has carried "what's actually on it" as an open item the whole time. Two things forced an answer now: the product itself has grown enough real, verified capabilities (TTS, voice cloning, Kie image/video) to actually describe, and a practical trigger — applying for a Payoneer payout account requires a live business website that shows specific verifiable information (see below).

The prior project (`voicica-ai`) already has a marketing site (`src/app/(home)/...`) with a visual style worth reusing (dark theme, hero → showcase → feature-grid → SEO-text page shape, `next-intl`-adjacent locale routing with `hreflang`/JSON-LD scaffolding). Its *content* does not carry over, for two independent reasons:

1. **Capability mismatch.** The old site covers `ai-voice`/`ai-image`/`ai-music`/`ai-video` *and* a whole separate product surface — Facebook/Instagram/TikTok/X/YouTube downloaders, generic image tools — none of which exist in this rewrite's scope (`product-scope.md` §1) and none of which are planned. Its content also monetizes via embedded native ads (`AdNativeBanner`) on every SEO page, a pattern that doesn't necessarily apply here (see Decision).
2. **Locale mismatch.** The old site's content is en/zh-CN/zh-TW/ja/ko. This project's target market is Thai/Indonesian/Spanish (`product-scope.md` §0) — a disjoint set. Only the *mechanism* (locale-prefixed URLs, `hreflang` alternates) is reusable, not a single sentence of copy.

**The Payoneer trigger, concretely**: Payoneer's website-verification step requires the page to show at least two of {full name, company-domain email, phone, email, an address matching the Payoneer profile, a photo}, on a page that isn't just a marketplace homepage. This is why `/contact` exists as its own page rather than being folded into a footer — its content (operator name, email, and — until verification clears — a real address) is answering a specific external requirement, not generic "get in touch" copy.

## Decision

**Page scope for this pass** — seven pages, matching what the product can actually back up today:

| Route | Content |
|---|---|
| `/` | Home: hero, capability overview, a real (text-only, see below) strip pulled from `GET /gallery`, CTA to sign up |
| `/voice` | TTS (multi-provider) + voice cloning |
| `/image` | Text-to-image / image-to-image (Kie) |
| `/video` | Image-to-video (Kie) |
| `/privacy` | Privacy Policy |
| `/terms` | Terms & Conditions |
| `/contact` | Operator name, email, address — drafted specifically to satisfy the Payoneer check above |

No pricing page yet (`product-scope.md` §2 — no real numbers or payment provider chosen, a placeholder page would just be noise) and no music page (no Kie models catalogued for it yet, `product-scope.md` §1). Both are additive later, same pattern as everything else in this codebase (add the page once there's something real to put on it).

**No ads on marketing pages.** `product-scope.md` §2 already scopes ads to Android specifically ("native ads on Android"); extending that to web marketing pages now, with zero traffic to justify it, would just be a monetization surface with no upside yet and a real downside (ad-cluttered SEO pages read worse to both visitors and search engines). Revisit if/when there's real traffic.

**Gallery preview on `/`: real data, text only, no media.** `GET /gallery` is genuinely unauthenticated (ADR 0010), so pulling real captions/counts onto the homepage is honest and free. But `GET /jobs/{id}/asset` — the only way to fetch the actual audio/image/video bytes — still requires *some* logged-in user (widened from owner-only to "any authenticated user" for Explore, not to "anyone"). A fully anonymous marketing visitor cannot play that media today. Rather than widen that auth boundary as a side effect of a marketing page (a real access-control change deserving its own discussion, not a silent side effect here), the homepage strip shows real captions/timestamps/type icons pulled from `GET /gallery`, no thumbnails or playback. Revisit if a public, no-login asset path is ever decided separately.

**i18n: reserve the content/SEO architecture, don't ship fake translations.** ADR 0013 decided locale-prefixed URLs for `(marketing)` but left English's own URL shape open. Resolved here, matching the old project's own convention: **English is the unprefixed default** (`/voice`, not `/en/voice`); a future Thai/Indonesian/Spanish page would live at `/th/...`/`/id/...`/`/es/...`, with `hreflang`'s `x-default` pointing at the unprefixed URL.

Only English ships in this pass. The `/th`, `/id`, `/es` prefixes are **not** registered yet — not built-and-empty, not machine-translated placeholders, genuinely not present, so hitting them 404s. This is deliberate: a Thai visitor landing on machine-translated copy is worse for trust and for SEO than not having a Thai page at all (auto-translated content is a well-documented ranking negative, not a neutral placeholder). What *is* built now, so that adding a language later is additive, not a rewrite:

- Content lives in a locale-keyed dictionary (`content/marketing/en.ts`), not scattered inline JSX strings — adding `content/marketing/th.ts` later is a content file, not a code change, same pattern as the Kie model catalog (`ADR 0015`) or the capability menu (`services/menu.py`).
- `lib/marketing-seo.ts`'s URL/`hreflang`-building helpers iterate a `MARKETING_LOCALES` registry (currently `[en]`) rather than hardcoding English — registering a new locale there is the one-line change that makes `hreflang` alternates and the sitemap include it.
- The actual `/th/...` etc. Next.js routes (a `[locale]` segment, or duplicated leaf `page.tsx` files depending on what App Router makes cleanest at the time) are **not** built yet — there's nothing to route to, and building untestable routing ahead of real content risks getting the shape wrong. This is the one genuinely deferred piece, called out explicitly rather than silently.

**Privacy Policy and Terms & Conditions are drafted as a real, usable first version** (not "Coming soon" placeholders) — covering what the product actually does (Firebase auth, credits, the specific third-party processors data passes through: Azure/Google/Fish Audio/Kie, Cloudflare R2 storage, no payment processor integrated yet). They are explicitly labeled in-app as a drafted starting point, not a substitute for a lawyer's review — needed for both the Payoneer application and any future payment-provider application, but real legal review before relying on them in a dispute is the user's call, not something this ADR can settle.

## Alternatives considered

- **Full parity with the old project's page count** (one SEO page per capability variant, complete pricing page, full legal suite up front). Rejected for this pass: real work for pages with no content to put on them yet (pricing) or no audience trigger yet (deeper legal pages beyond Privacy/Terms) — same "add it when there's something real" posture as the rest of this codebase.
- **Ship machine-translated `/th`, `/id`, `/es` content now** so the URLs exist immediately. Rejected — see i18n discussion above; a low-quality translated page is worse than no page, both for the visitor and for SEO.
- **Widen `GET /jobs/{id}/asset` to fully anonymous access** so the homepage gallery strip could show real media. Rejected as a decision to make *inside* this ADR — it's a real auth-boundary change (currently "any logged-in user", would become "anyone on the internet") that deserves its own discussion, not a side effect of a marketing page.

## Consequences

**Positive:** the marketing site launches with only real content — every page describes a capability that actually works end-to-end, every stat on the homepage is a real number from the real database, Privacy/Terms/Contact are substantive enough to support the Payoneer application today. The i18n architecture (content dictionary + locale registry) means adding Thai next is a translation task, not an engineering one.

**Negative / open items:**
- The actual `[locale]`-segment routing for `/th`/`/id`/`/es` is unbuilt; someone has to pick its concrete shape (dynamic segment vs. duplicated leaves) once there's real translated content to route to.
- No pricing page — `/contact` and `/voice`/`/image`/`/video` currently point signup-curious visitors straight at "Sign up" rather than a priced comparison; revisit once `product-scope.md` §2's pricing numbers are real.
- The Contact page's address is a real personal residential address, shown deliberately to satisfy Payoneer's verification checklist; the intent (confirmed with the user) is to remove or hide it once that verification clears — this ADR doesn't do that automatically, it's a manual follow-up.
- Privacy/Terms are a drafted starting point, not lawyer-reviewed — a real legal pass is still open before this should be relied on in an actual dispute or a stricter payment provider's compliance review.
