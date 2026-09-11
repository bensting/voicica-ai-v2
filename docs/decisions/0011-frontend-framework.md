# ADR 0011: Frontend Framework — Next.js

- Status: Accepted
- Date: 2026-09-11

## Context

[ADR 0005](0005-frontend-surfaces.md) settled `frontend/web`'s and `frontend/admin`'s *structure* (route-group-separated marketing/app in one deployable; admin physically separate) but explicitly left the framework itself as "TBD — assumed whatever it ends up being supports route-group-style internal separation." That gap needs to close before any real frontend code gets written.

## Decision

**Next.js (App Router)**, for both `frontend/web` and `frontend/admin`. Confirmed, not just carried over by default:

- **Directly resolves ADR 0005's hedge**: the App Router's route groups (`(marketing)` / `(app)`) are exactly the mechanism that ADR 0005 assumed would exist.
- **Proven in the prior project** with the same adjacent choices this rewrite is also making — TypeScript, Tailwind, Firebase Auth (`CLAUDE.md`'s prior-project reference) — real, validated experience to reuse rather than re-derive.
- **SSR/SSG fits the public surfaces specifically**: the marketing route group and the public gallery ([ADR 0010](0010-public-gallery-visibility-flag.md)) both benefit from server rendering/fast initial load and being crawlable — both are meant to work for a visitor with no account, including as a growth/conversion surface.

## Alternatives considered

Not deeply re-litigated — no concrete pain point (unlike Capacitor, where specific friction drove a change, [ADR 0005](0005-frontend-surfaces.md)) was raised against Next.js, and it already had validated experience from the prior project. Reusing that by default, only reconsidered if a real driver shows up, is the same posture applied elsewhere (e.g. keeping marketing+app merged until there's a concrete reason to split).

## Consequences

**Positive:** closes the last open "candidate, not confirmed" item in the frontend stack; `frontend/admin` uses the same framework as `frontend/web` (already assumed by ADR 0005), so there's one frontend toolchain to maintain, not two.

**Negative / trade-offs:** none specific to this choice beyond what ADR 0005 already accepted (Android gets no shared code with the web stack regardless of which web framework was picked).
