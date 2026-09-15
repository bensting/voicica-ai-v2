"""Minimal admin surface for this slice (ADR 0012's deferred-admin-scope note):
manual credit grants (stand-in for real top-up), job monitoring, capability
menu and Kie catalog CRUD, and reading/writing app_settings. Consumed by
`frontend/web`'s `(admin)` route group (ADR 0020) — every route stays
directly callable (curl, `/docs`) for anything the UI doesn't cover yet.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import (
    AdminJobResponse,
    CreditGrantRequest,
    KieCategoryAdmin,
    KieModelAdmin,
    KieModelPatch,
    MenuItemAdmin,
    MenuItemPatch,
    MeResponse,
    SettingUpdateRequest,
)
from app.core.auth import CurrentUser, require_admin
from app.core.db import get_db
from app.models.models import Job, User
from app.services import app_settings, credits
from app.services import kie_catalog as kie_catalog_service
from app.services import menu as menu_service

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


@router.get("/jobs", response_model=list[AdminJobResponse])
async def list_all_jobs(
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminJobResponse]:
    rows = (
        await db.execute(select(Job).order_by(Job.created_at.desc()).limit(100))
    ).scalars().all()
    return [AdminJobResponse.model_validate(row) for row in rows]


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


# ---- Capability menu (the "+" button's sheet) — one item at a time, not a
# raw settings blob PATCH, so an edit can't silently corrupt the other items
# (see services/menu.py's module docstring). ----


@router.get("/menu", response_model=list[MenuItemAdmin])
async def list_menu(
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MenuItemAdmin]:
    return await menu_service.list_for_admin(db)


@router.post("/menu", response_model=MenuItemAdmin, status_code=201)
async def create_menu_item(
    body: MenuItemAdmin,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MenuItemAdmin:
    try:
        item = await menu_service.create_item(db, body.model_dump(), updated_by=admin.id)
    except ValueError as exc:
        raise APIError(status_code=422, code="invalid_input", message=str(exc)) from exc
    await db.commit()
    return item


@router.patch("/menu/{item_id}", response_model=MenuItemAdmin)
async def update_menu_item(
    item_id: str,
    body: MenuItemPatch,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MenuItemAdmin:
    patch = body.model_dump(exclude_unset=True)
    try:
        item = await menu_service.update_item(db, item_id, patch, updated_by=admin.id)
    except KeyError as exc:
        raise APIError(status_code=404, code="not_found", message=str(exc)) from exc
    await db.commit()
    return item


@router.delete("/menu/{item_id}", status_code=204)
async def delete_menu_item(
    item_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await menu_service.delete_item(db, item_id, updated_by=admin.id)
    except KeyError as exc:
        raise APIError(status_code=404, code="not_found", message=str(exc)) from exc
    await db.commit()


# ---- Kie catalog (ADR 0015) — adding a model is meant to be exactly this:
# a POST here, no deploy, nothing else in the codebase touched. ----


@router.post("/kie-categories", response_model=KieCategoryAdmin, status_code=201)
async def create_kie_category(
    body: KieCategoryAdmin,
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> KieCategoryAdmin:
    try:
        row = await kie_catalog_service.create_category(db, body.model_dump())
    except ValueError as exc:
        raise APIError(status_code=422, code="invalid_input", message=str(exc)) from exc
    await db.commit()
    return row


@router.post("/kie-models", response_model=KieModelAdmin, status_code=201)
async def create_kie_model(
    body: KieModelAdmin,
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> KieModelAdmin:
    try:
        row = await kie_catalog_service.create_model(db, body.model_dump())
    except ValueError as exc:
        raise APIError(status_code=422, code="invalid_input", message=str(exc)) from exc
    await db.commit()
    return row


@router.patch("/kie-models/{model_id}", response_model=KieModelAdmin)
async def update_kie_model(
    model_id: str,
    body: KieModelPatch,
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> KieModelAdmin:
    patch = body.model_dump(exclude_unset=True)
    try:
        row = await kie_catalog_service.update_model(db, model_id, patch)
    except KeyError as exc:
        raise APIError(status_code=404, code="not_found", message=str(exc)) from exc
    await db.commit()
    return row


@router.delete("/kie-models/{model_id}", status_code=204)
async def delete_kie_model(
    model_id: str,
    _admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await kie_catalog_service.delete_model(db, model_id)
    except KeyError as exc:
        raise APIError(status_code=404, code="not_found", message=str(exc)) from exc
    await db.commit()
