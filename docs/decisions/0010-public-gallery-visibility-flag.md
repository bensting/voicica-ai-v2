# ADR 0010: Public Gallery Is a Visibility Flag, Not a Separate Content System

- Status: Accepted — **note ([ADR 0027](0027-public-asset-delivery-and-retention.md))**: asset files are now served from unguessable public R2 URLs, so `visibility` means "listed in the public gallery", not "nobody else can open the file".
- Date: 2026-09-11

## Context

Earlier discussion treated a "gallery" of shared user creations as if it might need its own content pipeline (a separate publish step, a distinct entity). Clarified: a gallery item is simply a job whose output the creator chose to make public — nothing more.

## Decision

- **`jobs.visibility`**: `private` (default) | `public`. Set by the owning user after a job succeeds — an explicit, opt-in action ("share to gallery"), never automatic/default-public.
- **A public gallery listing** reads jobs where `visibility = public` and their mirrored asset ([ADR 0004](0004-asset-mirroring-r2-retention.md)) is actually available, and **requires no login to view** — browsing is public, consistent with `frontend/web`'s `(marketing)` route group ([ADR 0005](0005-frontend-surfaces.md)). This does not relax [product-scope.md §1.1](../product-scope.md)'s "every capability requires login" — that's about *using* a capability (submitting a job); viewing already-public output someone else created is a different, unauthenticated action.

## Alternatives considered

- **A separate `gallery_items` table / publish pipeline.** Rejected as unneeded complexity for what's actually being asked — a visibility flag captures the whole request with far less new surface area. Revisit only if the gallery grows needs that don't fit naturally as job metadata (curation, comments, likes at scale).

## Consequences

**Positive:** minimal new schema (one column on an existing table); no separate publish pipeline; reuses the existing `jobs` + `assets` model entirely; an unauthenticated, browsable gallery is also a plausible answer to the still-open "what goes on the marketing site" question ([product-scope.md §3](../product-scope.md)).

**Negative / explicitly deferred, not blocking:**
- Whether a public job's asset should outlive the normal R2 retention window (ADR 0004) since other people, not just the creator, are viewing it — undecided.
- Moderation: auto-visible the moment a user opts in, vs. a review step first — undecided.
- Any richer gallery feature (search, curation, likes, comments) — out of scope until asked for.
