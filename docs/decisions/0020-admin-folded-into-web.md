# ADR 0020: Admin Folded into `frontend/web`, Not a Separate Deployment

- Status: Accepted
- Date: 2026-09-15

## Context

[ADR 0005](0005-frontend-surfaces.md) decided `frontend/admin` would be a physically separate Next.js project, separately deployed, from day one — explicitly rejecting a route-group-behind-a-role-check approach with the reasoning "a runtime role check is weaker than the code and bundle simply never reaching a non-admin client."

Nothing about that risk changed. What changed is the cost side of the trade-off becoming concrete rather than hypothetical: `frontend/admin` is still empty (a lone `.gitkeep`, zero code ever written against it) at the point real admin screens are finally needed — the backend's admin surface (`routes_admin.py`) already has full CRUD for the capability menu and the Kie catalog, credit grants, and job listing, with nothing to drive it but curl/scripts. Standing up a second Next.js project (its own auth wiring, its own copy of the design system, its own deploy target) to get a first CRUD screen shipped is real, immediate cost for a project with one maintainer, versus a route group inside `frontend/web` that reuses everything already built there.

Revisiting ADR 0005's own risk statement more precisely, rather than taking "physical vs. logical boundary" as a slogan: Next.js's App Router does route-based code splitting, so an `(admin)` route group's page code isn't bundled into `/` or `/app`'s JS. The real gap is narrower than "the whole admin bundle ships to every visitor" — **Next.js serves compiled client-JS chunks under `_next/static/` as public, unauthenticated static files, not gated by middleware** (middleware matches page/route requests, not typically `_next/static/*`). A sufficiently determined visitor could in principle fetch an admin route's compiled chunk directly, without ever passing a role check, learning what the admin UI looks like and what capabilities it exposes.

## Decision

**Fold admin into `frontend/web` as a third route group, `(admin)`, deployed as part of the same unit.** `frontend/admin/` is removed — no code was ever written against it.

This is accepted specifically because the actual data/mutation boundary was never the frontend's job in this codebase: every `/admin/*` backend route already depends on `require_admin` ([`core/auth.py`](../../backend/app/core/auth.py)), checking `role` — a Postgres column (`users.role`), not a Firebase custom claim, granted manually — independent of which frontend called it. **No frontend restructuring changes what an attacker can actually read or mutate.** What ADR 0005's boundary was really buying was narrower than "data protection": it was minimizing discoverability of the admin surface's existence and shape. That's a real but low-severity concern for a product with no real users yet and no secrets embedded in frontend code — worth mitigating cheaply, not worth a second deployable's ongoing cost at this stage.

Mitigations, so this is a deliberate trade-off and not just skipping the old boundary:

1. **`(admin)/layout.tsx` gates client-side**, same pattern `(app)/layout.tsx` already uses for its login gate: wait for Firebase auth state, then call `GET /me` and check `role` is `staff`/`admin`, redirecting immediately (before rendering any admin page content or firing any admin API call) if not. This is exactly the "runtime role check" ADR 0005 called weaker than a physical boundary — accepted here as the practical floor, not claimed as equivalent to one.
2. **Recommended, not yet done**: an edge-level gate (Cloudflare Access, or plain HTTP Basic Auth at the CDN in front of `/admin/*`) on top of the app-level check, closing the specific `_next/static` chunk-leak gap above without a second deployment. Deferred to whenever the Cloudflare side of this project is next touched — not blocking this reversal, since the chunk-leak risk is about discoverability, not data.
3. This ADR itself — the point of writing it down is that a real, sanctioned security boundary got weaker; it should be revisited (splitting `(admin)` back out is a folder move given the route-group boundary, same reasoning ADR 0005 already used for marketing/app) once any of ADR 0005's original drivers becomes real: a staff team beyond one person, a customer-data compliance requirement, or a genuine security review.

## Alternatives considered

- **Keep `frontend/admin` separate, just build it out now.** This is what ADR 0005 already decided — re-rejected here specifically on cost: zero code sunk, one maintainer, and the API-layer role check already provides the real protection regardless of which frontend calls it, so the marginal security benefit of a second deployable is small relative to its ongoing cost at this stage.
- **Edge-gate first, decide app structure after.** Rejected as a sequencing choice, not a substance one — the edge gate is complementary to, not a substitute for, the app-level role check (§1 above), and doesn't depend on which repo/deployable admin lives in. Listed as a follow-up (§2), not blocking this ADR.

## Consequences

**Positive:** admin screens ship against `frontend/web`'s existing design system, auth wiring, and deploy pipeline — no second Next.js project to bootstrap or maintain. The real security boundary (`require_admin` at the API layer) is unaffected by this change either way.

**Negative / open items:** the specific `_next/static` chunk-discoverability gap this ADR names is real and unmitigated until the edge-level gate (§2) is added — accepted for now, not solved. If `frontend/web` and `frontend/admin` are ever split again, that's on this ADR's own reasoning: revisit once a concrete driver (staff team size, compliance, a security review) appears, not preemptively.
