# ADR 0008: Auth Provider — Firebase Auth

- Status: Accepted
- Date: 2026-09-11

## Context

Every capability requires login ([product-scope.md §1.1](../product-scope.md)), across three client-facing surfaces ([ADR 0005](0005-frontend-surfaces.md)): `frontend/web`, `frontend/admin` (same users, gated by role), and `android/`. The backend needs to verify identity on essentially every request.

Firebase Auth was the prior project's choice and worked there (`CLAUDE.md` lists it as reusable experience). The one reason to avoid it — Firebase is a Google Cloud product with known reachability problems inside mainland China, which would directly conflict with this rewrite's core priority of consumer-facing latency/reliability ([product-scope.md §0](../product-scope.md)) for that user segment — doesn't apply: **mainland China is confirmed not a target market for this rewrite.**

## Decision

**Firebase Auth**, used the same way across the client-facing surfaces:

- `frontend/web` and `android/` use Firebase's native SDKs for sign-in (email/password, plus social providers as needed later).
- `frontend/admin` uses the same Firebase Auth (same `users`, same sign-in flow) — staff access is gated by `users.role`, not a separate identity system.
- The backend verifies every request's Firebase ID token via the **Firebase Admin SDK**, wrapped behind a swappable interface (`core/auth.py`: something like `verify_identity(token) -> (user_id, role)`) rather than called directly from route handlers. This mirrors [ADR 0001](0001-provider-adapter-layer.md)'s principle — applied to auth instead of AI providers: if Firebase is ever replaced (e.g. this decision gets revisited because market scope changes), the change is contained to this module, not scattered across every route.
- `users.id` = the Firebase UID ([data-model.md](../data-model.md), now confirmed rather than a candidate).
- `users.role` (`user` / `staff` / `admin`) is a locally-managed column, not derived from Firebase custom claims — admin access control lives entirely in our own DB, not dependent on Firebase claim-propagation timing.

## Alternatives considered

- **Self-hosted auth** (backend-issued JWT sessions, our own password hashing / phone+OTP). This was the leading alternative specifically because of the mainland-China reachability risk — with that risk confirmed not applicable, it's rejected for now: it adds real security-critical engineering surface (password storage, OTP delivery and rate-limiting, token refresh) with no offsetting benefit here. Revisit if the target market ever expands to mainland China.
- **WeChat login / other China-specific identity providers.** Rejected for the same reason — not a target market.

## Consequences

**Positive:** fastest path to working auth across three surfaces; reuses validated experience from the prior project; Firebase's SDKs absorb token refresh, social login, and password-reset flows instead of us building them.

**Negative / trade-offs:** a real dependency on Firebase/Google's reachability and pricing going forward — acceptable given the confirmed target market, but the `core/auth.py` abstraction above is specifically what keeps a future reversal (if market scope ever changes) contained rather than a full rewrite.
