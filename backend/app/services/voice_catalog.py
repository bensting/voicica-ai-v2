"""Read/write access to `voice_catalog` (docs/data-model.md, ADR 0007) —
a synced mirror of each provider's own voice list, never hand-edited.
Written wholesale by app/scheduled/sync_catalog.py; read by GET
/catalog/voices and /catalog/languages (the voice picker) and by
services/jobs.py submit_tts (resolving a chosen voice to the provider +
provider_voice_id to call).

Two corrections already made to this module, both from real user feedback
on the picker, kept here so the reasoning survives:

1. An earlier version defaulted GET /catalog/voices (no `locale` given) to
   only the th/id/es target market — reasoning: growth's region priority
   (product-scope.md §0) meant the picker shouldn't ship a multi-thousand
   -voice payload nobody would pick from. Wrong premise: real traffic
   speaks every language, English included — target market was ever only
   about infra region, not which voices a user can choose. Fixed by not
   restricting availability, and keeping the payload small differently:
   fetch one selection at a time (below), never the whole catalog.

2. The picker then selected by *exact locale* (`es-MX`, `es-AR`, ...).
   Azure and Google don't carve up a language into countries the same
   way — Azure has ~22 Spanish locales, Google has 2 — so a locale-level
   dropdown is really "Azure's Spanish taxonomy, occasionally joined by
   Google," not a real per-provider choice. Fixed by grouping by *base
   language* (`es`, not `es-MX`) for selection — list_languages() groups
   `locale`'s text before the first "-"; list_voices()'s `language` param
   prefix-matches on it — while every provider's actual locale variants
   for that language still come back in the result, each voice showing
   its own specific locale (frontend/web/lib/locale-names.ts).
"""

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import VoiceCatalog

_BASE_LANGUAGE = func.split_part(VoiceCatalog.locale, "-", 1)


async def list_voices(
    db: AsyncSession,
    *,
    provider: str | None = None,
    locale: str | None = None,
    language: str | None = None,
) -> list[VoiceCatalog]:
    """`locale` is an exact match ("es-MX"); `language` is a base-language
    prefix match ("es" -> every es-* locale from every provider). The
    picker uses `language`; `locale` stays available for anything that
    genuinely wants one exact provider-specific variant."""
    query = select(VoiceCatalog)
    if provider:
        query = query.where(VoiceCatalog.provider == provider)
    if locale:
        query = query.where(VoiceCatalog.locale == locale)
    elif language:
        query = query.where(
            or_(VoiceCatalog.locale == language, VoiceCatalog.locale.like(f"{language}-%"))
        )
    query = query.order_by(VoiceCatalog.locale, VoiceCatalog.display_name)
    return list((await db.execute(query)).scalars().all())


async def list_languages(db: AsyncSession, *, provider: str | None = None) -> list[tuple[str, int]]:
    """Distinct base languages present in the catalog (the part of `locale`
    before its first "-"), with a voice count each — cheap enough to
    populate a language dropdown without fetching every voice just to read
    off `.locale` (list_voices does that part, lazily, once picked)."""
    query = select(_BASE_LANGUAGE, func.count()).group_by(_BASE_LANGUAGE)
    if provider:
        query = query.where(VoiceCatalog.provider == provider)
    query = query.order_by(_BASE_LANGUAGE)
    return list((await db.execute(query)).all())


async def get_voice(db: AsyncSession, voice_id: uuid.UUID) -> VoiceCatalog | None:
    """Used by submit_tts to resolve a user's voice pick to
    provider/provider_voice_id/locale — the thing that decides which adapter
    the request actually gets routed to (ADR 0001's registry, by name)."""
    return await db.get(VoiceCatalog, voice_id)


async def replace_provider_catalog(
    db: AsyncSession, *, provider: str, rows: list[dict]
) -> int:
    """Wholesale overwrite of one provider's slice of the catalog (the sync
    strategy data-model.md documents — simpler and safer than diffing, since
    this table has no FK depending on a row's id surviving a resync: jobs
    store provider_voice_id directly, not a voice_catalog foreign key)."""
    await db.execute(delete(VoiceCatalog).where(VoiceCatalog.provider == provider))
    for row in rows:
        db.add(VoiceCatalog(provider=provider, **row))
    await db.commit()
    return len(rows)
