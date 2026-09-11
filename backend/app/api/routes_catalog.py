"""GET /catalog/voices and /catalog/languages — the voice picker's data
(docs/api-contract.md "Catalog"), read from voice_catalog (ADR 0007).
No target-market restriction, and selection groups by base language
(not exact locale) — see services/voice_catalog.py's module docstring for
both corrections and why. Required-auth by the same "default consistency,
easy to relax later" reasoning as the rest of this API's soft-call
endpoints — see api-contract.md's note."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LanguageOption, VoiceCatalogResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import voice_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/voices", response_model=list[VoiceCatalogResponse])
async def list_voices(
    provider: str | None = Query(default=None, description="azure | google | fish_audio"),
    locale: str | None = Query(default=None, description="exact match, e.g. th-TH"),
    language: str | None = Query(
        default=None, description="base-language prefix match, e.g. es -> every es-* locale"
    ),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VoiceCatalogResponse]:
    voices = await voice_catalog.list_voices(db, provider=provider, locale=locale, language=language)
    return [VoiceCatalogResponse.model_validate(v) for v in voices]


@router.get("/languages", response_model=list[LanguageOption])
async def list_languages(
    provider: str | None = Query(default=None, description="azure | google | fish_audio"),
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LanguageOption]:
    """Populates the voice picker's language dropdown without fetching every
    voice just to read off `.locale` — pick a language here, then GET
    /catalog/voices?language=... for every matching voice across providers."""
    rows = await voice_catalog.list_languages(db, provider=provider)
    return [LanguageOption(language=language, voice_count=count) for language, count in rows]
