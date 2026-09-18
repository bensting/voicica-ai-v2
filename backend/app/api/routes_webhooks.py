"""POST /webhooks/kie — Kie's `callBackUrl` target (ADR 0015,
architecture.md §3d): the primary Kie-completion path, with
`worker/cron.py`'s poll sweep as the fallback for anything missed.

No signature/secret to verify — not documented by Kie, so this endpoint
trusts only `taskId` to find *a* job, then re-derives everything else via
`provider.poll()` rather than the webhook body itself (`services/jobs.py`
`finalize_kie_job`'s own docstring explains why: one source of truth for
what a terminal Kie job looks like). That keeps the blast radius of a
forged/replayed call low — at worst it triggers a redundant, harmless
`recordInfo` poll for a `taskId` an attacker would already have to know;
it can't fabricate a result or move credits on its own."""

import logging
from typing import Any

import stripe
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.core.config import get_settings
from app.core.db import get_db
from app.models.models import Job
from app.providers.registry import get_provider_by_name
from app.services import billing, jobs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/kie", status_code=200)
async def kie_webhook(payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    task_id = (payload.get("data") or {}).get("taskId") or payload.get("taskId")
    if not task_id:
        return {"ok": False}

    job = (
        await db.execute(select(Job).where(Job.provider_job_id == task_id))
    ).scalar_one_or_none()
    if job is None:
        # Not necessarily an error — a retried/duplicate callback for a job
        # this backend never actually submitted (or already knows by a
        # different id) shouldn't 500 and cause Kie to keep retrying.
        return {"ok": False}

    provider = get_provider_by_name("kie")
    job_status = await provider.poll(task_id)
    await jobs.finalize_kie_job(db, job.id, job_status)
    return {"ok": True}


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    """The one path that actually credits a wallet for a Stripe purchase
    (ADR 0024) — unlike Kie's webhook above, Stripe's payload *is* trusted
    (after signature verification), since Stripe's own `construct_event`
    is exactly what proves the body wasn't forged; there's no equivalent of
    Kie's `poll()` to independently re-derive "did this really get paid."

    Signature verification is why this reads the raw body via `Request`
    instead of a parsed Pydantic model — `construct_event` needs the exact
    bytes Stripe signed, not a body FastAPI has already decoded and could
    re-serialize slightly differently."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise APIError(status_code=503, code="billing_unavailable", message="Webhook not configured.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise APIError(status_code=400, code="invalid_signature", message=str(exc)) from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # This version of the stripe SDK's `construct_event` returns a real
        # `stripe.checkout.Session` object, not a plain dict — it supports
        # `session["key"]` (subscript access) but *not* `.get(...)` (a real
        # dict method), which raises its own explicit AttributeError rather
        # than silently returning None. Caught live on the first real
        # webhook delivery, not assumed correct from reading the SDK docs.
        purchase = await billing.complete_purchase(
            db,
            checkout_session_id=session["id"],
            payment_intent_id=session["payment_intent"],
        )
        if purchase is None:
            # A session id Stripe knows about but we don't (e.g. a stray
            # test-mode event from a different Stripe account/CLI listener)
            # — logged, not raised, so Stripe doesn't retry something that
            # will never resolve.
            logger.warning("Stripe webhook: no CreditPurchase for session %s", session["id"])
    else:
        logger.info("Stripe webhook: unhandled event type %s", event["type"])

    return {"ok": True}
