# frontend/web

Next.js app (ADR 0011) implementing the `(app)` route group's TTS slice — see the repo root [README](../../README.md) and [`docs/`](../../docs/README.md) for the architecture. `(marketing)` doesn't exist yet (product-scope.md's open item).

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
- `app/login/` — sign in / sign up.
- `app/(app)/` — everything behind login (ADR 0005): `layout.tsx` gates on Firebase auth state and renders the bottom nav; `page.tsx` is Home (a "your creations" list — no separate wallet card, the header's credits pill already shows balance, a duplicate card was cut on review); `create/tts/` is the TTS flow (submit → inline result with playback + the public/private toggle); `me/` is the profile + full history.

Visual language follows the prior project's native app (dark, gradient CTA — see the design canvas from earlier in this project's history) with new typefaces (Bricolage Grotesque + Hanken Grotesk, `app/layout.tsx`) rather than system fonts.

## Verified

Signed up a real account through the actual browser UI, submitted a real TTS job, played the resulting audio back (through the backend's asset proxy, not a raw R2 URL — see `backend/README.md`), and confirmed the credit balance, history entry, and public/private toggle all reflect reality. Not mocked at any layer.

## Not built yet

`(marketing)` route group, voice picker (no voice catalog endpoint exists server-side yet), the public gallery page (no `/gallery` endpoint yet — ADR 0010's mechanism is done backend-side, browsing isn't wired up), Android, real payment top-up (the "Top up" button doesn't do anything yet).
