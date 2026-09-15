# ADR 0005: Frontend Surfaces — One Web App, Separate Admin, Native Android

- Status: Accepted
- Date: 2026-09-11

## Context

The original plan was one website (marketing + authenticated product app) with Android as a Capacitor-wrapped shell around it (the prior project's pattern). Two things changed that assumption:

1. Real, specific Android friction: saving generated files to the gallery (Android's scoped storage), integrating native ad SDKs, and runtime permission handling are all awkward through a WebView bridge — and this friction is inherent to wrapping a web app on Android, not specific to Capacitor's plugin ecosystem. AI-assisted development also lowers the cost of building and maintaining a fully native Android UI enough to change the trade-off.
2. A genuine need for an admin/management surface emerged (user management, credit adjustments, job monitoring, Kie model-catalog and pricing config) — a different audience and security profile than either the marketing site or the authenticated product app.

## Decision

Four frontend surfaces, every one a plain consumer of the same backend API — no surface talks to a provider or holds business logic itself, reinforcing the backend-owns-everything principle from `CLAUDE.md`:

1. **`frontend/web`** — one Next.js project ([ADR 0011](0011-frontend-framework.md); its App Router route groups are exactly the internal-separation mechanism this ADR needs) holding both the public marketing pages and the authenticated product app, separated internally by route groups (`(marketing)` / `(app)`) with an auth boundary enforced in middleware, deployed as a single unit. No SEO/traffic/team-scaling driver exists yet to justify a physical split into two deployables; the route-group boundary is strict enough in code that splitting later, if a concrete driver appears, is a folder move rather than a redesign.
2. **`frontend/admin`** — a separate Next.js project (same framework as `frontend/web`), separately deployed, staff-only auth. Physically separate **from day one** — this is a security-boundary decision, not a scaling one: admin routes and bundle must never ship to a customer's browser. **Reversed by [ADR 0020](0020-admin-folded-into-web.md)**: `frontend/admin` was never built (stayed empty from this ADR's writing until admin screens were actually needed), and admin now lives in `frontend/web` as an `(admin)` route group instead — see that ADR for why the trade-off changed.
3. **`android/`** — a native Kotlin/Compose app calling the backend API directly. No WebView wrapper. The Android-specific friction described above doesn't go away by swapping wrapping frameworks (Capacitor vs. a hand-rolled WebView bridge); going native removes it entirely, and the ongoing cost of a second UI implementation is judged acceptable given AI-assisted development speed.

## Alternatives considered

- **Wrap the website in Capacitor for Android** (the original plan, matching the prior project). Rejected: the specific pain points (storage, ads, permissions) are inherent to any WebView-wrapped approach on Android, not fixable by swapping the wrapping framework.
- **Split marketing and product app into separate deployables now.** Rejected for now: no concrete driver yet (independent release cadence, a dedicated content team, SEO scaling needs). Revisit if one appears — kept cheap via the route-group boundary.
- **Fold admin routes into the authenticated web app behind a role check.** Rejected: a runtime role check is weaker than the code and bundle simply never reaching a non-admin client. The security boundary should be physical, not just logical. **This is exactly what [ADR 0020](0020-admin-folded-into-web.md) later decided to do anyway**, once `frontend/admin` reaching this point still empty made the cost side of that trade-off concrete rather than hypothetical — see that ADR for the reasoning and what it does to mitigate the risk named here.

## Consequences

**Positive:**
- Android gets full native capability (file system, ads, permissions, notifications) with no bridging friction.
- ~~Admin has a hard security boundary from day one.~~ Reversed by ADR 0020 before any admin UI was built.
- Marketing + product app stays one simple deployable while there are zero users, with a cheap path to split later.
- Every surface — web app, admin, Android — is confirmed to be a pure API consumer; no backend change was needed to support adding native Android as a fourth client, which validates the design in ADR 0002/0003 (the job + credits API was already shaped to be client-agnostic).

**Negative / trade-offs:**
- Android now means maintaining a second UI implementation of the core product flows (submit a generation job, poll it, spend credits, view history) in Kotlin — not just a thin wrapper. Real, ongoing cost, accepted given the specific friction points this avoids.
- No shared design system between the web app and Android (different platforms/languages) — visual consistency has to be maintained by a shared design spec/convention, not shared code.
- The marketing/product-app split is deferred, not solved — needs revisiting once (if) a concrete driver shows up.

## Open items

- Admin's exact feature scope (which config becomes a proper CRUD UI vs. stays a direct config-file edit) is not decided here — deferred.
