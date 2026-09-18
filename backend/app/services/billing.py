"""Credit-pack purchases via Stripe Checkout — one-time payments only, no
subscriptions (ADR 0024). `app_settings.credit_packages` (ADR 0012) holds the
sellable packs; this module turns a chosen pack into a real Stripe Checkout
Session, then applies a completed session's payment to the wallet exactly
once, no matter how many times Stripe redelivers the webhook for it.
"""

import uuid
from typing import Any

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import CreditPurchase
from app.services import app_settings, credits

_PACKAGES_KEY = "credit_packages"


class UnknownPackageError(Exception):
    pass


class StripeNotConfiguredError(Exception):
    pass


async def list_packages(db: AsyncSession) -> list[dict[str, Any]]:
    return await app_settings.get_setting(db, _PACKAGES_KEY)


async def _get_package(db: AsyncSession, package_key: str) -> dict[str, Any]:
    packages = await list_packages(db)
    for package in packages:
        if package["key"] == package_key:
            return package
    raise UnknownPackageError(package_key)


async def create_checkout_session(
    db: AsyncSession, *, user_id: str, package_key: str, success_url: str, cancel_url: str
) -> str:
    """Creates a real Stripe Checkout Session (mode="payment", one-time —
    never "subscription") for the given pack, and a matching `pending`
    `CreditPurchase` row *before* returning the URL, so a webhook that
    arrives later always has a real row to find and lock — there's no
    window where a paid session exists with nothing on our side to apply it
    to. Returns the Checkout Session's own hosted URL; the caller redirects
    the browser there directly (no Stripe.js/publishable key needed for
    this flow — that's only for embedded/Payment-Element checkouts)."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise StripeNotConfiguredError("STRIPE_SECRET_KEY is not set")

    package = await _get_package(db, package_key)
    purchase_id = uuid.uuid4()

    session = stripe.checkout.Session.create(
        api_key=settings.stripe_secret_key,
        mode="payment",
        client_reference_id=user_id,
        # Not trusted for crediting the wallet (the webhook re-reads the
        # session by id instead, same "never trust the callback body alone"
        # posture as Kie's webhook, architecture.md §3d) — carried only so
        # a support lookup in the Stripe Dashboard can find the right user/
        # purchase row without a DB query.
        metadata={"user_id": user_id, "package_key": package_key, "purchase_id": str(purchase_id)},
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": package["price_usd_cents"],
                    "product_data": {
                        "name": f"Voicica credits — {package['label']} ({package['credits']} credits)",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
    )

    db.add(
        CreditPurchase(
            id=purchase_id,
            user_id=user_id,
            package_key=package_key,
            credits=package["credits"],
            amount_usd_cents=package["price_usd_cents"],
            stripe_checkout_session_id=session.id,
            status="pending",
        )
    )
    await db.commit()
    return session.url


async def complete_purchase(
    db: AsyncSession, *, checkout_session_id: str, payment_intent_id: str | None = None
) -> CreditPurchase | None:
    """Applies a completed Checkout Session's payment to the buyer's wallet
    — the one place this happens, called only from the Stripe webhook
    (`POST /webhooks/stripe`). `SELECT ... FOR UPDATE` on the purchase row
    is the same idempotency idiom `finalize_kie_job` already uses for Kie's
    own at-least-once webhook delivery: Stripe's webhooks carry the same
    guarantee, so a redelivered `checkout.session.completed` for a purchase
    already marked `completed` finds the row locked, sees it's no longer
    `pending`, and safely no-ops instead of crediting the wallet twice."""
    purchase = (
        await db.execute(
            select(CreditPurchase)
            .where(CreditPurchase.stripe_checkout_session_id == checkout_session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if purchase is None or purchase.status != "pending":
        return purchase

    await credits.topup(db, user_id=purchase.user_id, amount=purchase.credits)
    purchase.status = "completed"
    purchase.completed_at = func.now()
    purchase.stripe_payment_intent_id = payment_intent_id
    await db.commit()
    return purchase
