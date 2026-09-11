"""Orchestrates job submission and owns the hold -> settle/release lifecycle
(ADR 0002 + ADR 0003). This slice implements `tts` end-to-end; every other
capability's submit flow follows the same shape.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Asset, CreditHold, Job
from app.providers.base import JobRef
from app.providers.registry import get_provider_by_name
from app.services import assets as assets_service
from app.services import credits
from app.services import voice_catalog as voice_catalog_service


async def submit_tts(
    db: AsyncSession,
    *,
    user_id: str,
    text: str,
    voice_id: uuid.UUID,
    speed: float = 1.0,
    volume: int = 50,
    pitch: int = 50,
    visibility: str = "private",
) -> Job:
    """Submit a TTS job. Raises credits.InsufficientCreditsError before
    anything reaches a provider if the user can't afford the estimated cost;
    raises ValueError if voice_id doesn't match a known voice_catalog row.

    Which provider gets called is decided by the voice, not the capability:
    a voice_catalog row carries its own provider + provider_voice_id + locale
    (docs/data-model.md), so picking a voice IS picking a provider.
    `voice_id` is required — Fish Audio isn't a general "no voice selected"
    fallback, it's reserved for a user's own cloned voices (ADR 0009, not
    yet built); there is no product-sensible default voice to fall back to
    without one (an earlier version of this defaulted to Fish Audio's own
    generic voice, which had nothing to do with what the picker actually
    offers — schemas.TTSRequest.voice_id has no default for the same reason).

    speed/volume/pitch use one provider-agnostic scale (schemas.TTSRequest:
    speed 0.5-2.0x, volume/pitch 1-100 centered on 50) passed through to
    every adapter as-is; each converts to its own units — ranges and exact
    formulas ported from the prior project's verified-in-production
    conversions (`ai-voice-labs-web`'s azure-tts.ts/google-tts.ts/queue/tts
    route.ts), not re-derived from scratch:
      - Azure (SSML <prosody>): rate% = (speed-1)*100, pitch% = pitch-50,
        volume = volume as-is (0-100). Always wraps the voice in <prosody> —
        the defaults (0%, 0%, 50) are themselves a no-op.
      - Google (audioConfig): speakingRate = speed clamped to Google's wider
        0.25-4.0; pitch = (pitch-50)*0.4 (their -20..20 semitone range);
        volumeGainDb = (volume-50)*0.2 (their -96..16 dB range, kept modest).
        Some newer voices (Chirp3 HD) reject `pitch` outright — the adapter
        retries once without it on that specific 400, same as the prior
        project's fallback.
      - Fish Audio: only supports speed + volume, no pitch (silently
        ignored, matching the prior project's own comment on why). Included
        in the request only when they differ from default, in Fish's own
        prosody shape: speed as-is, volume as (volume-50)/50 (their ~-1..1
        relative scale)."""
    estimated_cost = await credits.estimate_tts_cost(db, text)

    voice = await voice_catalog_service.get_voice(db, voice_id)
    if voice is None:
        raise ValueError(f"Unknown voice_id={voice_id!r}")
    provider_name = voice.provider
    provider_voice_id = voice.provider_voice_id
    locale = voice.locale

    job = Job(
        user_id=user_id,
        capability="tts",
        provider=provider_name,
        status="pending",
        input={
            "text": text,
            "voice_id": str(voice_id),
            "speed": speed,
            "volume": volume,
            "pitch": pitch,
        },
        estimated_cost=estimated_cost,
        # ADR 0010: opt-in at creation time (in addition to PATCH /jobs/{id}
        # afterward) — still gated on the job actually succeeding, same as
        # the PATCH path (a failed job never gets a mirrored asset to show).
        visibility=visibility if visibility == "public" else "private",
    )
    db.add(job)
    await db.flush()  # assigns job.id

    credit_hold = await credits.hold(db, user_id=user_id, job_id=job.id, amount=estimated_cost)
    job.hold_id = credit_hold.id

    provider = get_provider_by_name(provider_name)
    provider_inputs: dict[str, Any] = {
        "text": text,
        "speed": speed,
        "volume": volume,
        "pitch": pitch,
        "provider_voice_id": provider_voice_id,
        "locale": locale,
    }
    job_ref: JobRef = await provider.submit("tts", provider_inputs)

    if job_ref.status == "succeeded":
        await _complete_success(db, job=job, credit_hold=credit_hold, job_ref=job_ref)
    elif job_ref.status == "failed":
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
    else:
        # Azure/Google never return pending/processing — this branch exists
        # because the interface (ADR 0002) is shared with async providers
        # (Kie, later; Fish Audio too, once voice cloning training exists).
        job.status = job_ref.status
        job.provider_state = job_ref.provider_state

    # Commit explicitly here rather than relying solely on get_db()'s
    # post-yield commit: a client that immediately polls GET /jobs/{id} right
    # after this response must see the committed row, not a race against
    # request-teardown timing. (get_db()'s own commit becomes a harmless
    # no-op on top of this.)
    await db.commit()
    return job


async def _complete_success(
    db: AsyncSession, *, job: Job, credit_hold: CreditHold, job_ref: JobRef
) -> None:
    output = job_ref.output or {}
    audio_bytes: bytes | None = output.get("audio_bytes")
    content_type = output.get("content_type", "audio/mpeg")

    # TTS cost is exact from the request text up front — no post-hoc divergence
    # to reconcile (unlike Kie, where actual_cost can differ, ADR 0003).
    actual_cost = job.estimated_cost
    await credits.settle(db, credit_hold, actual_cost)

    asset_fields: dict[str, Any] = {}
    if audio_bytes:
        extension = "mp3" if "mpeg" in content_type else "wav"
        asset_fields = await assets_service.upload_bytes(
            job_id=job.id, data=audio_bytes, content_type=content_type, extension=extension
        )
        db.add(
            Asset(
                job_id=job.id,
                r2_key=asset_fields["r2_key"],
                mirror_status=asset_fields["mirror_status"],
                mirrored_at=asset_fields["mirrored_at"],
                expires_at=asset_fields["expires_at"],
            )
        )

    job.status = "succeeded"
    job.actual_cost = actual_cost
    job.completed_at = datetime.now(UTC)
    # A relative path the client fetches through us (with its normal auth
    # header), not a raw R2 URL — see assets.download_bytes for why presigned
    # URLs aren't used here.
    asset_url = f"/jobs/{job.id}/asset" if asset_fields else None
    job.output = {"asset_url": asset_url}


async def _complete_failure(
    db: AsyncSession, *, job: Job, credit_hold: CreditHold, error: str | None
) -> None:
    await credits.release(db, credit_hold)
    job.status = "failed"
    job.error = error
    job.completed_at = datetime.now(UTC)


async def get_job(db: AsyncSession, job_id: uuid.UUID, *, user_id: str) -> Job | None:
    """Read a job's current state. For this slice every job is already
    terminal by the time it's written (Azure/Google are both synchronous) —
    there's nothing to poll yet. An async provider's poll would call
    `provider.poll()` here and advance the row before returning it; not
    needed until Kie."""
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        return None
    return job


async def get_job_with_asset(db: AsyncSession, job_id: uuid.UUID, *, user_id: str) -> Job | None:
    """Same as `get_job`, but with `.asset` eagerly loaded (selectinload) —
    for `GET /jobs/{id}/asset`, which needs the R2 key. `db.get()`'s default
    lazy relationship access isn't awaitable outside an explicit loader in an
    async session, hence the separate query shape rather than reusing `get_job`.

    Unlike `get_job`, this allows a *public* job's asset through for any
    logged-in user, not just the owner (ADR 0010 — gallery items are meant
    to be played by other people; the caller here is still authenticated,
    since Explore/gallery browsing lives behind the app's login for now, but
    ownership specifically shouldn't gate a public job's audio)."""
    job = (
        await db.execute(select(Job).options(selectinload(Job.asset)).where(Job.id == job_id))
    ).scalar_one_or_none()
    if job is None or (job.user_id != user_id and job.visibility != "public"):
        return None
    return job
