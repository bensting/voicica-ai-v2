"""Read/write access to `voice_catalog` (docs/data-model.md, ADR 0007) —
a synced mirror of each provider's own voice list, never hand-edited.
Written wholesale by app/scheduled/sync_catalog.py; read by GET
/catalog/voices and /catalog/locales (the voice picker) and by
services/jobs.py submit_tts (resolving a chosen voice to the provider +
provider_voice_id to call).

An earlier version of this module defaulted GET /catalog/voices (no
`locale` given) to only the th/id/es target market — reasoning: growth's
region priority (product-scope.md §0) meant the picker shouldn't ship a
multi-thousand-voice payload almost entirely made of languages nobody
would pick. Wrong premise: real traffic (marketing, organic signups)
speaks every language, including English — target market was ever only
about infra region, not about which voices a user can choose. Fixed by
NOT restricting availability at all, and instead keeping the payload
small a different way: the picker fetches one language at a time
(list_voices with an explicit `locale`, like the old project's
useVoices() hook), never the whole catalog in one call. list_locales()
exists so the picker's language dropdown can be populated without
pulling every voice just to read off their locale field.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import VoiceCatalog


async def list_voices(
    db: AsyncSession, *, provider: str | None = None, locale: str | None = None
) -> list[VoiceCatalog]:
    query = select(VoiceCatalog)
    if provider:
        query = query.where(VoiceCatalog.provider == provider)
    if locale:
        query = query.where(VoiceCatalog.locale == locale)
    query = query.order_by(VoiceCatalog.locale, VoiceCatalog.display_name)
    return list((await db.execute(query)).scalars().all())


async def list_locales(db: AsyncSession, *, provider: str | None = None) -> list[tuple[str, int]]:
    """Distinct locales present in the catalog, with a voice count each —
    cheap enough to populate a language dropdown without fetching every
    voice just to read off `.locale` (list_voices does that part, lazily,
    once a locale is picked)."""
    query = select(VoiceCatalog.locale, func.count()).group_by(VoiceCatalog.locale)
    if provider:
        query = query.where(VoiceCatalog.provider == provider)
    query = query.order_by(VoiceCatalog.locale)
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
