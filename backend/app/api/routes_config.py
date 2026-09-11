"""GET /config/menu — the "+" button's sheet, resolved to one locale.
See docs/api-contract.md's "Capability menu" section."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MenuItemResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import menu

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/menu", response_model=list[MenuItemResponse])
async def get_menu(
    locale: str = Query(default="en", description="th | id | es | en (falls back to en)"),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MenuItemResponse]:
    return await menu.list_for_client(db, locale=locale)
