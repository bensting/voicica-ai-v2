# frontend/web

Next.js app (ADR 0011) implementing the `(app)` route group's TTS slice — see the repo root [README](../../README.md) and [`docs/`](../../docs/README.md) for the architecture. `(marketing)` doesn't exist yet (product-scope.md's open item); `/` is a placeholder redirect (auth state → `/app` or `/login`) until it does — **`/` must stay reserved for it**, the authenticated app lives under a literal `/app` URL prefix, not the root (a route group alone doesn't affect the URL; the `app/(app)/app/` folder nesting is what actually puts `/app` in the path — caught and fixed once already, don't regress it).

## Setup

```bash
npm install
cp .env.local.example .env.local   # fill in NEXT_PUBLIC_FIREBASE_* (already has real values — see below) and NEXT_PUBLIC_API_BASE_URL
npm run dev
```

Or in PyCharm/WebStorm: the **"Web"** run configuration (`.run/Web.run.xml`, checked into the repo) runs `npm run dev` against this project — pick it from the run-configuration dropdown. It uses the project's configured Node interpreter, not a hardcoded path.

The Firebase web config in `.env.local.example` is already filled in — it's meant to be public (see the file's own comment) — project `ai-voice-labs-473713`, reused from the prior project on purpose (`CLAUDE.md`). `NEXT_PUBLIC_API_BASE_URL` should point at the backend (`http://localhost:8000` for local dev, per `backend/README.md`).

## What's here

- `lib/firebase.ts` / `lib/auth-context.tsx` — Firebase Auth (email/password + Google, both enabled on the shared Firebase project), exposed via `useAuth()`.
- `lib/api.ts` — the one place that calls the backend: attaches the Firebase ID token, unwraps `docs/api-contract.md`'s `{"error": {code, message}}` envelope into a typed `ApiError`.
- `lib/locale.ts` — `(app)`'s locale preference, a cookie not a URL segment ([ADR 0013](../../docs/decisions/0013-i18n-routing-strategy.md)).
- `app/login/` — sign in / sign up.
- `app/page.tsx` — root placeholder: redirects to `/app` (signed in) or `/login` (signed out). Temporary until `(marketing)` exists.
- `app/(app)/app/` — everything behind login (ADR 0005), served at `/app`: `layout.tsx` (one level up, `app/(app)/layout.tsx`) gates on Firebase auth state and renders the bottom nav; `page.tsx` is Home (a "your creations" list — no separate wallet card, the header's credits pill already shows balance, a duplicate card was cut on review); `create/tts/` is the TTS flow (submit → inline result with playback + the public/private toggle); `me/` is the profile + full history.
- `components/BottomNav.tsx` + `components/CreateSheet.tsx` — the "+" button opens a bottom sheet, not a direct link. **The sheet's contents are entirely server-driven** (`GET /config/menu`, `docs/api-contract.md`'s "Capability menu" section / `backend/app/services/menu.py`) — labels, routes, enabled/disabled, order, badges, all come from the backend, already resolved to one locale. The frontend's only local config is `components/icons.tsx`, a small icon-key → SVG lookup (the one deliberate exception — "前端基本上没有任何配置" doesn't cover presentational icon markup). Only the TTS item is enabled right now; the other four (dialogue/image/bg-remove/video-download) exist in the seed data disabled, waiting on their own backend slices.
- `public/brand/` — the prior project's logo assets, reused as-is (`mark.webp`/`mark-512.webp` for the toucan mark, `credits-token.png` for the credits pill icon) — see `CLAUDE.md` on why: the old logo was good, no reason to redo it.

Visual language follows the prior project's native app (dark, gradient CTA — see the design canvas from earlier in this project's history) with new typefaces (Bricolage Grotesque + Hanken Grotesk, `app/layout.tsx`) rather than system fonts.

## Verified

Signed up a real account through the actual browser UI, submitted a real TTS job, played the resulting audio back (through the backend's asset proxy, not a raw R2 URL — see `backend/README.md`), and confirmed the credit balance, history entry, and public/private toggle all reflect reality. Not mocked at any layer.

## Not built yet

`(marketing)` route group, voice picker (no voice catalog endpoint exists server-side yet), the public gallery page (no `/gallery` endpoint yet — ADR 0010's mechanism is done backend-side, browsing isn't wired up), Android, real payment top-up (the "Top up" button doesn't do anything yet), a top-left settings/language drawer (agreed direction, not built — this is what will eventually call `lib/locale.ts`'s `setLocale()`).

**i18n routing** ([ADR 0013](../../docs/decisions/0013-i18n-routing-strategy.md)): `(marketing)` will use locale-prefixed URLs once it exists; `(app)` uses a plain cookie (`lib/locale.ts`'s `getLocale()`/`setLocale()`) — already wired into `CreateSheet`'s `GET /config/menu` call, just nothing writes the cookie yet since the language switcher isn't built.
