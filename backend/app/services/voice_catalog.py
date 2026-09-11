"""Read/write access to `voice_catalog` (docs/data-model.md, ADR 0007) —
a synced mirror of each provider's own voice list, never hand-edited.
Written wholesale by app/scheduled/sync_catalog.py; read by GET
/catalog/voices (the voice picker) and by services/jobs.py submit_tts
(resolving a chosen voice to the provider + provider_voice_id to call).
"""

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import VoiceCatalog

# product-scope.md §0's target market. GET /catalog/voices with no explicit
# `locale` scopes to these by default — the voice picker gets a ~270-voice
# payload instead of the full multi-language catalog (2800+ rows, almost all
# of it languages this product doesn't serve). Structural/product config
# (ADR 0012's file-not-table category, not an ops-tunable scalar) — revisit
# only if the target market itself changes. Pass an explicit `locale` to
# bypass this (e.g. future admin tooling browsing the whole catalog).
_TARGET_MARKET_LOCALE_PREFIXES = ("th", "id", "es")


async def list_voices(
    db: AsyncSession, *, provider: str | None = None, locale: str | None = None
) -> list[VoiceCatalog]:
    query = select(VoiceCatalog)
    if provider:
        query = query.where(VoiceCatalog.provider == provider)
    if locale:
        query = query.where(VoiceCatalog.locale == locale)
    else:
        query = query.where(
            or_(*(VoiceCatalog.locale.like(f"{p}-%") for p in _TARGET_MARKET_LOCALE_PREFIXES))
        )
    query = query.order_by(VoiceCatalog.locale, VoiceCatalog.display_name)
    return list((await db.execute(query)).scalars().all())


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
