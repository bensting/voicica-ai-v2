"""Read/write access to `voice_catalog` (docs/data-model.md, ADR 0007) —
a synced mirror of each provider's own voice list, never hand-edited.
Written wholesale by app/scheduled/sync_catalog.py; read by GET
/catalog/voices (the voice picker) and by services/jobs.py submit_tts
(resolving a chosen voice to the provider + provider_voice_id to call).
"""

import uuid

from sqlalchemy import delete, select
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
