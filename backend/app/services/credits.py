"""Credit ledger: pricing lookup + the hold -> settle/release lifecycle (ADR 0003).

`CreditWallet.balance` is the single source of truth for what a user actually
has; it's mutated directly (not derived by summing `credit_transactions`).
`credit_transactions` rows for `hold`/`release` are an audit/event trail of the
reservation lifecycle, not themselves balance mutations — only `topup` and
`settle` rows correspond to a real change in `balance`. Available balance for
a new hold is always `balance - sum(active holds)`, computed live from
`credit_holds`, never cached.
"""

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CreditHold, CreditTransaction, CreditWallet
from app.services import app_settings


class InsufficientCreditsError(Exception):
    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(f"need {required} credits, only {available} available")


async def estimate_tts_cost(db: AsyncSession, text: str) -> int:
    rate = await app_settings.get_setting(db, "tts_credits_per_10_chars")
    return max(1, math.ceil(len(text) / 10) * rate)


async def _get_wallet(db: AsyncSession, user_id: str) -> CreditWallet:
    wallet = (
        await db.execute(select(CreditWallet).where(CreditWallet.user_id == user_id))
    ).scalar_one_or_none()
    if wallet is None:
        raise LookupError(f"user {user_id!r} has no wallet — did first-login bootstrap run?")
    return wallet


async def available_balance(db: AsyncSession, user_id: str) -> int:
    wallet = await _get_wallet(db, user_id)
    held = (
        await db.execute(
            select(func.coalesce(func.sum(CreditHold.amount), 0)).where(
                CreditHold.user_id == user_id, CreditHold.status == "active"
            )
        )
    ).scalar_one()
    return wallet.balance - held


async def hold(db: AsyncSession, user_id: str, job_id: uuid.UUID, amount: int) -> CreditHold:
    """Reserve `amount` credits before a job is submitted to a provider.
    Raises InsufficientCreditsError before the request ever reaches a vendor."""
    balance = await available_balance(db, user_id)
    if balance < amount:
        raise InsufficientCreditsError(required=amount, available=balance)

    wallet = await _get_wallet(db, user_id)
    credit_hold = CreditHold(user_id=user_id, job_id=job_id, amount=amount, status="active")
    db.add(credit_hold)
    await db.flush()  # assigns credit_hold.id
    db.add(CreditTransaction(wallet_id=wallet.id, type="hold", amount=-amount, job_id=job_id))
    return credit_hold


async def settle(db: AsyncSession, credit_hold: CreditHold, actual_cost: int) -> None:
    """Job succeeded: debit `actual_cost` (the only real balance mutation here)
    and release whatever's left of the hold."""
    wallet = await _get_wallet(db, credit_hold.user_id)
    wallet.balance -= actual_cost
    credit_hold.status = "settled"
    credit_hold.resolved_at = func.now()
    db.add(
        CreditTransaction(
            wallet_id=wallet.id, type="settle", amount=-actual_cost, job_id=credit_hold.job_id
        )
    )
    leftover = credit_hold.amount - actual_cost
    if leftover > 0:
        db.add(
            CreditTransaction(
                wallet_id=wallet.id, type="release", amount=leftover, job_id=credit_hold.job_id
            )
        )


async def release(db: AsyncSession, credit_hold: CreditHold) -> None:
    """Job failed: release the entire hold. No debit — matches Kie's own
    behavior of never charging for a failed generation, applied to every
    provider uniformly (ADR 0003)."""
    wallet = await _get_wallet(db, credit_hold.user_id)
    credit_hold.status = "released"
    credit_hold.resolved_at = func.now()
    db.add(
        CreditTransaction(
            wallet_id=wallet.id, type="release", amount=credit_hold.amount, job_id=credit_hold.job_id
        )
    )


async def topup(db: AsyncSession, user_id: str, amount: int, updated_by: str | None = None) -> None:
    """Add credits directly — used by the signup bonus and by the admin manual
    credit-grant endpoint (the stand-in for real top-up, ADR: payment provider TBD)."""
    wallet = await _get_wallet(db, user_id)
    wallet.balance += amount
    db.add(CreditTransaction(wallet_id=wallet.id, type="topup", amount=amount))
