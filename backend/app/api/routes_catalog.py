"""GET /catalog/voices and /catalog/locales — the voice picker's data
(docs/api-contract.md "Catalog"), read from voice_catalog (ADR 0007).
No target-market restriction — see services/voice_catalog.py's module
docstring for why an earlier version of this had one and doesn't anymore.
Required-auth by the same "default consistency, easy to relax later"
reasoning as the rest of this API's soft-call endpoints — see
api-contract.md's note."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LocaleOption, VoiceCatalogResponse
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


@router.get("/locales", response_model=list[LocaleOption])
async def list_locales(
    provider: str | None = Query(default=None, description="azure | google | fish_audio"),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocaleOption]:
    """Populates the voice picker's language dropdown without fetching every
    voice just to read off `.locale` — pick a locale here, then GET
    /catalog/voices?locale=... for that language's actual voices."""
    rows = await voice_catalog.list_locales(db, provider=provider)
    return [LocaleOption(locale=locale, voice_count=count) for locale, count in rows]
