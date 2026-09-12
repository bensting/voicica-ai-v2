"""Read/delete access to `voice_models` — a user's own cloned voices
(docs/data-model.md, ADR 0009). Training (create) is a job submission, so
it lives in `services/jobs.py` (`submit_voice_model_training`) alongside
`submit_tts`, not here — this module is just the CRUD-ish rest of it.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import VoiceModel
from app.providers.registry import get_provider_by_name

logger = logging.getLogger(__name__)


async def list_ready(db: AsyncSession, *, user_id: str) -> list[VoiceModel]:
    """GET /voice-models — only `ready` ones (api-contract.md): a `training`
    row shouldn't be usable yet (nothing to pick), and a `failed` one is
    dead weight the user never asked to keep around. Fish Audio's
    `train_mode="fast"` (the only mode used here) is synchronous, so in
    practice a row is `ready` moments after `POST /voice-models` returns —
    there's no real "still training" state to poll for in this slice."""
    rows = (
        await db.execute(
            select(VoiceModel)
            .where(VoiceModel.user_id == user_id, VoiceModel.state == "ready")
            .order_by(VoiceModel.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_owned(db: AsyncSession, voice_model_id: uuid.UUID, *, user_id: str) -> VoiceModel | None:
    voice_model = await db.get(VoiceModel, voice_model_id)
    if voice_model is None or voice_model.user_id != user_id:
        return None
    return voice_model


async def delete(db: AsyncSession, voice_model_id: uuid.UUID, *, user_id: str) -> bool:
    """DELETE /voice-models/{id}, owner-only. Deletes at the provider first
    (best-effort — matching the prior project's own comment: continue with
    the local delete even if the remote call fails, rather than leaving an
    orphaned row the user can never remove because Fish Audio's side is
    already gone or erroring)."""
    voice_model = await get_owned(db, voice_model_id, user_id=user_id)
    if voice_model is None:
        return False

    try:
        provider = get_provider_by_name(voice_model.provider)
        await provider.delete_voice_model(voice_model.provider_model_id)
    except Exception:
        # Best-effort: an orphaned local row the user can never remove
        # (because the remote call keeps failing) is worse than a model left
        # behind at Fish Audio — same tradeoff the prior project's own
        # comment on this made.
        logger.warning(
            "Failed to delete voice_model %s at provider %s (removing local row anyway)",
            voice_model_id, voice_model.provider, exc_info=True,
        )

    await db.delete(voice_model)
    await db.commit()
    return True
