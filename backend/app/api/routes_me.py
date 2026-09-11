"""GET /me — docs/api-contract.md "Identity / wallet"."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MeResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services.credits import available_balance

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    balance = await available_balance(db, user.id)
    return MeResponse(id=user.id, email=user.email, role=user.role, balance=balance)
