# ADR 0024: Credit Purchases via Stripe Checkout, One-Time Only

- Status: Accepted
- Date: 2026-09-18

## Context

Every credit a user has ever had came from one of two sources: the signup bonus, or an admin manually granting some (`services/credits.py topup()`, its own docstring calling itself out as "the stand-in for real top-up until a payment provider is chosen" from the day it was written). `docs/product-scope.md`'s payment mechanism has been an explicit open item since the project's very first pass ([ADR 0012](0012-app-settings-table.md) references it, never resolves it).

The trigger this time was concrete rather than a scheduling decision: the user applied for and set up a real Payoneer account, then a real Stripe account, specifically to get this unblocked — not a hypothetical "we'll need this eventually." Stripe was chosen over Payoneer for the actual checkout integration after checking Payoneer's own current developer offering: "Payoneer Checkout" (their equivalent product) is, as of this check, only accepting early applications from merchants with a **Hong Kong legal entity** — the account here is an *Individual* business type in Thailand, not eligible to even apply. Stripe, by contrast, explicitly supports an `Individual` business type for a Thailand-based account (confirmed against Stripe's own Thailand-specific onboarding documentation, not assumed), making it the only one of the two actually usable today.

## Decision

**Three fixed, one-time credit packs — no subscriptions, no metered billing.** Real pricing, decided by the user, not a placeholder:

| Key | Label | Credits | Price | Per-credit |
|---|---|---|---|---|
| `small` | Starter | 1,000 | $9.00 | $0.0090 |
| `medium` | Pro | 12,500 | $99.00 | $0.0079 |
| `large` | Studio | 29,500 | $199.00 | $0.0067 |

Volume-discounted per credit as the pack size grows (a standard, deliberate shape — the "why" is a business decision, not an engineering one, so it isn't re-litigated here beyond noting the curve is monotonic and sane). Stored as `app_settings.credit_packages` (ADR 0012's existing "structured, admin-editable, JSON blob" category — the same shape `capability_menu` already uses), not a new dedicated table: three rows that change only when a human decides to change pricing, no independent lifecycle of their own the way `kie_models` earns its own table for (ADR 0015's own distinction — a catalog that "grows one row at a time" vs. a handful of values a human tunes). Editable anytime via the already-generic `PATCH /admin/settings/credit_packages`, no new admin endpoint needed.

**Stripe Checkout (hosted), not a custom Payment Element form.** `POST /billing/checkout` creates a real `stripe.checkout.Session` (`mode="payment"`, one-time) and returns its hosted URL directly — the browser is redirected there, no Stripe.js or publishable key needed on the frontend at all for this flow (that's only required for an *embedded* Checkout or Payment Element). Card details never touch this backend or `frontend/web`, sidestepping PCI scope entirely for the fastest-to-ship version of this feature, matching this project's "AI-native, speed-first, but not at the expense of reliability" posture — this isn't the corner to cut speed on custom-building.

**A `credit_purchases` row is created `pending` at session-creation time, before Stripe has been paid anything** — not only once a webhook confirms success. This closes a real gap the alternative (create the row only when the webhook fires) would have: without it, a webhook naming a session id this backend never recorded would have nothing to apply the payment to. Creating the row up front means there's always something to find.

**Idempotency via `SELECT ... FOR UPDATE`, the same idiom `finalize_kie_job` already uses (ADR 0015).** Stripe's webhook delivery is at-least-once, not exactly-once — the exact same class of guarantee that arq's redelivery already forced a fix for once (ADR 0014's own "Negative/open items", the Grok video double-submission incident). `services/billing.py complete_purchase()` locks the `credit_purchases` row by its Stripe Checkout Session id, checks `status == "pending"` under that lock, and only then calls `credits.topup()` — a redelivered `checkout.session.completed` for an already-`completed` purchase finds the row already resolved and no-ops, rather than crediting the wallet twice. This was designed in from the start here, not bolted on after a real duplicate-charge incident the way Kie's version was — a lesson already paid for once, applied proactively the second time a webhook-driven completion path got built.

**The webhook body is trusted, unlike Kie's.** Kie's webhook (`architecture.md §3d`) deliberately trusts nothing from the callback payload itself — it only uses the `taskId` to look up *a* job, then re-derives the real outcome via a fresh `poll()` call, because Kie documents no signature scheme to prove a callback wasn't forged. Stripe is the opposite case: `stripe.Webhook.construct_event()` cryptographically verifies the payload against a per-endpoint signing secret before anything in `POST /webhooks/stripe` looks at it, so the verified body itself *is* the source of truth — there's no equivalent "re-poll Stripe to make sure" step needed or possible (a Checkout Session doesn't have a richer independent status to re-fetch that would add real assurance beyond what the signed event already proves).

**Two new settings, following the project's existing "differs by environment" documentation habit** (`backend/README.md`'s Deploy table, already covering `CORS_ALLOW_ORIGINS`/`PUBLIC_BASE_URL`/`FIREBASE_CREDENTIALS_PATH`): `STRIPE_SECRET_KEY` (test-mode locally, live in production — never the reverse) and `STRIPE_WEBHOOK_SECRET` (genuinely different per endpoint — the Stripe CLI's local `stripe listen` and the real Dashboard-registered production endpoint each mint their own). A third new setting, `FRONTEND_BASE_URL`, was added rather than reusing `CORS_ALLOW_ORIGINS[0]` — that setting is an *allow-list* (can legitimately hold more than one real origin, e.g. apex + `www`, ADR 0023) and `PUBLIC_BASE_URL` is this *backend's* own URL, not the frontend's; Checkout's `success_url`/`cancel_url` need a browser redirect target, which is neither of those things, so conflating it into an existing setting would have been the wrong kind of reuse.

## Alternatives considered

- **Payoneer Checkout.** Rejected for now, not on technical merit — currently gated to Hong Kong legal entities only, which this account isn't. Revisit if that gate lifts.
- **A custom Stripe Payment Element / embedded form.** Rejected for this pass — more control over the checkout page's look, but real added scope (PCI considerations, more frontend state to manage, Stripe.js integration) for a first payment feature that doesn't need that yet. Hosted Checkout can be swapped for this later without touching the backend's session-creation contract much.
- **Subscriptions / metered billing.** Rejected — the user's own call ("一次性购买即可"), and it matches how credits already work everywhere else in this product (a wallet balance, not a recurring entitlement).
- **Crediting the wallet directly from the Checkout success redirect, not the webhook.** Rejected — a browser landing on `success_url` only proves the browser navigated there, not that Stripe actually confirmed payment (a user could reach that URL without ever paying, e.g. by guessing/bookmarking it). The webhook, signature-verified, is the only trustworthy signal; the success page is UX only (tell the user to check back), never the thing that moves credits.

## Consequences

**Positive:** the project's oldest open item (`docs/product-scope.md`'s payment mechanism) is finally resolved with a real, working payment provider — not a placeholder. The idempotency design avoids repeating the exact double-processing incident ADR 0014 already had to learn from once.

**Negative / open items:**
- **Not yet verified against real Stripe test-mode API calls** — written and reviewed, migration applied to the real database, routes confirmed registered (`/openapi.json`), but the actual `create_checkout_session` → real test-mode payment → webhook → wallet-credited round trip is still pending a real Stripe test secret key. This ADR will be updated with that verification once it happens, not left silently claiming more confidence than earned.
- **No frontend UI yet** — `POST /billing/checkout` and `GET /billing/packages` exist; `frontend/web` has no "buy credits" screen calling them yet.
- **No real-time notification when credits actually land** — unlike job completion (ADR 0018's SSE push), a successful purchase doesn't notify the frontend live; the success redirect URL (`/app/me?purchase=success`) is a hint to re-check the wallet balance, not a guarantee it's already updated by the time the page loads (the webhook can arrive after the browser redirect does). Acceptable for a first pass; a real fix would extend ADR 0018's event channel to a non-job event type.
- **Currency is USD only** — the target market (product-scope.md §0: Thai/Indonesian/Spanish) will see Stripe's own currency-conversion/localized-price display at checkout (Stripe handles this automatically), not native local-currency pricing set by this product. Revisit if conversion friction turns out to matter.
- **No refund flow, no proration, no failed-payment retry UX** — out of scope for a first version whose only job is "prove a real purchase can credit a real wallet, exactly once."
