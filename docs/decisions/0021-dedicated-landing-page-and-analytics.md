# ADR 0021: Dedicated Landing Page (`/get`) + Analytics

- Status: Accepted
- Date: 2026-09-15

## Context

The homepage (`/`, ADR 0019) works for organic visitors browsing the site, but the user now has a concrete need it doesn't serve: a single URL to hand to every future traffic source — paid ads, social, QR codes, whatever comes next — with two real conversion paths behind it: a production Android app (a real Play Store listing, `ai.voicica.app` — this project's own records still said "Android not started," now stale) and the existing web product. Two things this needs that the homepage doesn't have: zero distraction (the homepage's header/footer link to `/voice`, `/image`, `/video`, exactly the exits a page whose only job is converting shouldn't offer), and a way to actually measure which channel sends traffic — nothing in this codebase records a page view today.

## Decision

**A dedicated route, `/get`, outside `(marketing)`'s layout entirely** — its own minimal shell (`app/get/layout.tsx`): logo (non-clickable, not even back to `/`), the two conversion actions, and only the legally-necessary footer links (Privacy/Terms). No nav, no links to any other page. `noindex, follow` in its metadata (organic search shouldn't surface a page whose pitch duplicates the homepage's; ad platforms' own review crawlers still need to fetch it normally, so it isn't `robots.txt`-disallowed the way `/app`/`/admin` are).

**One page, not one per channel.** Traffic-source attribution is a job for URL query parameters (`utm_source`/`utm_campaign`/etc., the standard every ad platform already appends) plus an analytics tool, not for maintaining near-duplicate pages per channel. Revisit only if a specific channel's audience ever needs genuinely different messaging, not preemptively.

**The primary CTA is decided server-side**, not client-side after the fact: `/get`'s page component reads the request's own `User-Agent` header (`next/headers`) and picks Android vs. web as the primary action before the first byte renders — no hydration flash where the wrong button shows then swaps. Both actions are always present regardless (this page's only two exits), just reordered by which one a visitor in that situation is more likely to want.

**Analytics: GA4 via Firebase Analytics**, not a second, separate `gtag.js`/script tag. Firebase Analytics *is* GA4 under the hood (same Measurement ID, same reports) — the Firebase JS SDK is already a dependency here for auth, so this adds an SDK call (`getAnalytics()`), not a new script. Reuses the Measurement ID (`G-RWBX15PP30`) that was already sitting in `.env.local.example`, commented out, from the prior project's shared Firebase project (`ai-voice-labs-473713`) — consistent with that project already being intentionally reused (ADR 0008), and it turned out to carry real, already-linked Google Ads conversion tracking (`AW-11504012045`), confirmed live in real network traffic once wired up, not something built fresh here. Scoped to marketing-facing surfaces only — `(marketing)`'s layout and `/get`'s layout — never the authenticated `(app)`/`(admin)` route groups, which don't need ad/campaign analytics and shouldn't carry the extra script weight.

`lib/firebase.ts`'s `getFirebaseAnalytics()` returns `null` (never throws) when `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` is unset or the browser doesn't support it (`isSupported()` — rules out some in-app/webview browsers, no IndexedDB) — analytics being unavailable must never break the page it's trying to measure. `components/Analytics.tsx` logs a `page_view` on mount and on every pathname change (Next.js client-side navigation never fires a real page load, so this can't be left to a classic multi-page-site `gtag.js` snippet to handle automatically) and exposes `logCtaClick()` for the two conversion actions specifically (`select_content`, `item_id: "download_android" | "get_started_web"`) — fire-and-forget, never awaited, so a slow/dropped analytics call can't delay the actual navigation it's measuring.

**The official Google Play badge SVG** was ported from the prior project's own assets (`public/images/stores/google-play-badge.svg`, a standard Google-provided badge, not custom art) rather than approximated — consistent with this project's existing practice of reusing real brand/store assets (`CLAUDE.md` on the logo).

## Alternatives considered

- **Fold this into the existing homepage.** Rejected — the user specifically wants clean per-channel attribution and a page with no exits besides the two real conversion actions; the homepage is deliberately more explorable (nav to Voice/Image/Video, the real gallery strip's own "Create your own" link, etc.) and shouldn't be stripped down to serve both jobs at once.
- **A landing page per traffic channel** (`/get/tiktok`, `/get/google`, ...). Rejected for now — UTM parameters plus an analytics tool already solve channel attribution without N near-duplicate pages to maintain; revisit only if a channel's messaging genuinely needs to differ.
- **Client-side `navigator.userAgent` sniffing** for the primary CTA. Rejected in favor of server-side detection (`next/headers`) specifically to avoid a first-paint flash of the wrong button.
- **A fresh GA4 property instead of reusing the old project's.** Considered, not chosen for this pass — the existing one is free, already linked to a real Google Ads account, and swapping the Measurement ID later is a one-line env var change, not a re-architecture, if a clean split ever matters.

## Consequences

**Positive:** one canonical URL now exists to hand to any future traffic source, with real, verified analytics (confirmed via real network requests, not assumed) recording page views and which of the two conversion actions a visitor took. Adding a language to this page later, or a genuinely channel-specific variant, is additive — nothing here was built to assume English/one-channel-only in a way that blocks that.

**Negative / open items:**
- No UTM-to-signup attribution yet — this pass measures page views and CTA clicks, not which campaign a completed signup came from; that needs a small backend addition (persisting acquisition source at signup) and wasn't asked for yet.
- Post-install Android attribution (did a Play Store click actually convert to an install+open) isn't tracked — that needs the Play Install Referrer API wired into the Android app itself, out of scope here.
- Reusing the old project's GA4/Google Ads property means this page's traffic isn't cleanly separated from whatever that property saw before — acceptable for now (see Alternatives), revisit if that mixing ever actually causes a reporting problem.
