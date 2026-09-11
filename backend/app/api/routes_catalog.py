"""GET /catalog/voices — the synced voice list (docs/api-contract.md
"Catalog"), read from voice_catalog (ADR 0007). With no `locale` given,
scopes to the target market (services/voice_catalog.py) rather than
returning the full multi-language catalog. Required-auth by the same
"default consistency, easy to relax later" reasoning as the rest of this
API's soft-call endpoints — see api-contract.md's note."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import VoiceCatalogResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import voice_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/voices", response_model=list[VoiceCatalogResponse])
async def list_voices(
    provider: str | None = Query(default=None, description="azure | google | fish_audio"),
    locale: str | None = Query(default=None, description="e.g. th-TH"),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VoiceCatalogResponse]:
    voices = await voice_catalog.list_voices(db, provider=provider, locale=locale)
    return [VoiceCatalogResponse.model_validate(v) for v in voices]
