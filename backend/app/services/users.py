"""First-login bootstrap: create the local `users` row + wallet + signup
bonus the first time a verified Firebase identity is seen (flow #10,
docs/flows.md; bonus amount from ADR 0012's `app_settings`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CreditWallet, User
from app.services import app_settings, credits


async def get_or_create_user(db: AsyncSession, *, uid: str, email: str) -> User:
    user = await db.get(User, uid)
    if user is not None:
        return user

    user = User(id=uid, email=email, role="user")
    db.add(user)
    await db.flush()

    db.add(CreditWallet(user_id=uid, balance=0))
    await db.flush()

    bonus = await app_settings.get_setting(db, "signup_bonus_credits")
    await credits.topup(db, user_id=uid, amount=bonus)

    return user
