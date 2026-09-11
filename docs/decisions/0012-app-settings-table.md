# ADR 0012: Simple Tunable Values Live in `app_settings`, Not Config Files

- Status: Accepted
- Date: 2026-09-11

## Context

[`data-model.md`](../data-model.md) already decided Kie's model catalog and pricing rules start as a static config file, promoted to a database table only once `frontend/admin` needs to edit them live. That rule fits Kie's catalog because it's structurally complex (per-model input schemas) and curated by engineering.

Two new values came up that don't fit that mold: the TTS credit rate (credits per character) and the new-signup credit bonus. Both are single scalars, and both are the kind of thing a non-engineer (growth/ops) plausibly wants to tune on a Tuesday afternoon — not a structural, engineering-curated catalog.

## Decision

Split "config" into two categories, going forward:

- **Structural/engineering config** — Kie's model catalog, provider priority/fallback order, R2 retention windows. Unchanged: stays a file, promoted to a table only when a proven live-edit need shows up ([data-model.md](../data-model.md)).
- **Simple scalar business/ops settings** — the TTS credit rate, the signup bonus, and future values like it (a referral bonus, a daily free-credit drip, etc.). These live in a generic key-value table, `app_settings` (`key`, `value` (jsonb), `updated_at`, `updated_by`), **from day one** — trivial to store, and the whole point is that they're editable without waiting on a deploy.

Admin's minimal scope for the current slice ([ADR 0005](0005-frontend-surfaces.md)'s deferred detail) gains one generic capability: `GET /admin/settings`, `PATCH /admin/settings/{key}`. Still no bespoke UI — callable via script for now, same posture as the rest of this slice's admin surface (manual credit grant, job monitoring).

Seeded initial values (placeholders, tunable anytime, not a business decision this ADR is making): `signup_bonus_credits = 500`, `tts_credits_per_10_chars = 1`.

## Alternatives considered

- **Put these in the same config file as Kie's catalog.** Rejected: conflates an engineering-curated structural catalog with a business lever someone outside engineering wants to flip, and forces a deploy for either kind of change — the wrong cost for the business-lever category specifically.

## Consequences

**Positive:** pricing rate and signup bonus are tunable without a deploy from day one; a generic settings table + two endpoints covers this and every future scalar setting like it, no bespoke schema or UI per value.

**Negative / open items:** no versioning or audit trail on settings changes yet (who changed what, when) — add if that becomes a real need, not speculatively now. Exactly which future values qualify as "simple scalar setting" vs. warrant their own structured table is a case-by-case call, not a formula.
