"""Minimal admin surface for this slice (ADR 0012's deferred-admin-scope note):
manual credit grants (stand-in for real top-up), job monitoring, and reading/
writing app_settings. No `frontend/admin` UI yet — call these with a script.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import CreditGrantRequest, JobResponse, MeResponse, SettingUpdateRequest
from app.core.auth import CurrentUser, require_admin
from app.core.db import get_db
from app.models.models import Job, User
from app.services import app_settings, credits

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users/{user_id}", response_model=MeResponse)
async def get_user(
    user_id: str,
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise APIError(status_code=404, code="not_found", message="No such user.")
    balance = await credits.available_balance(db, user_id)
    return MeResponse(id=user.id, email=user.email, role=user.role, balance=balance)


@router.post("/users/{user_id}/credits", response_model=MeResponse)
async def grant_credits(
    user_id: str,
    body: CreditGrantRequest,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """The stand-in for real top-up until a payment provider is chosen
    (product-scope.md §2). `reason` is required so this stays auditable via
    credit_transactions even without a dedicated admin-action log yet."""
    user = await db.get(User, user_id)
    if user is None:
        raise APIError(status_code=404, code="not_found", message="No such user.")

    await credits.topup(db, user_id=user_id, amount=body.amount, updated_by=admin.id)
    await db.commit()  # see the comment in services/jobs.py submit_tts — same reasoning
    balance = await credits.available_balance(db, user_id)
    return MeResponse(id=user.id, email=user.email, role=user.role, balance=balance)


@router.get("/jobs", response_model=list[JobResponse])
async def list_all_jobs(
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    rows = (
        await db.execute(select(Job).order_by(Job.created_at.desc()).limit(100))
    ).scalars().all()
    return [JobResponse.model_validate(row) for row in rows]


@router.get("/settings", response_model=dict[str, Any])
async def get_settings_(
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await app_settings.list_settings(db)


@router.patch("/settings/{key}")
async def update_setting(
    key: str,
    body: SettingUpdateRequest,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await app_settings.set_setting(db, key, body.value, updated_by=admin.id)
    await db.commit()  # see the comment in services/jobs.py submit_tts — same reasoning
    return {"key": row.key, "value": body.value}
