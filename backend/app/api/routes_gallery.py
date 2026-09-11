"""GET /gallery — docs/api-contract.md "Gallery" (ADR 0010). Public: no
auth dependency, on purpose — browsing what other users chose to share
requires no login, same as the rest of this route's contract says."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import GalleryItemResponse, GalleryPage
from app.core.db import get_db
from app.services import gallery

router = APIRouter(tags=["gallery"])


@router.get("/gallery", response_model=GalleryPage)
async def list_gallery(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> GalleryPage:
    jobs, next_cursor = await gallery.list_public(db, cursor=cursor, limit=limit)
    return GalleryPage(
        items=[GalleryItemResponse.model_validate(j) for j in jobs], next_cursor=next_cursor
    )
