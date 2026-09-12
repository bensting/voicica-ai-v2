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

from app.models.models import Asset, CreditHold, Job, VoiceModel
from app.providers.base import JobRef
from app.providers.registry import get_provider_by_name
from app.services import app_settings, credits
from app.services import assets as assets_service
from app.services import voice_catalog as voice_catalog_service


async def submit_tts(
    db: AsyncSession,
    *,
    user_id: str,
    text: str,
    voice_id: uuid.UUID | None = None,
    voice_model_id: uuid.UUID | None = None,
    speed: float = 1.0,
    volume: int = 50,
    pitch: int = 50,
    visibility: str = "private",
) -> Job:
    """Submit a TTS job. Raises credits.InsufficientCreditsError before
    anything reaches a provider if the user can't afford the estimated cost;
    raises ValueError if voice_id/voice_model_id doesn't resolve to a real,
    owned voice.

    Which provider gets called is decided by the voice, not the capability —
    exactly one of two kinds of voice is given (schemas.TTSRequest enforces
    this with a model_validator, so this function trusts it's already true):
    - `voice_id`: a `voice_catalog` row, which carries its own provider +
      provider_voice_id + locale (docs/data-model.md) — picking a voice IS
      picking a provider.
    - `voice_model_id`: a `voice_models` row (ADR 0009) — a voice the caller
      has cloned themselves. Currently always `provider="fish_audio"` (the
      only provider this slice's cloning is built against); the row must
      belong to `user_id` and be `state="ready"`, or this raises ValueError.
    Neither is optional at the HTTP layer — Fish Audio isn't a general "no
    voice selected" fallback (an earlier version of this defaulted to its
    own generic voice, which had nothing to do with what the picker actually
    offers), so there is no product-sensible default to fall back to.

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

    locale: str | None = None
    if voice_model_id is not None:
        owned_voice = await db.get(VoiceModel, voice_model_id)
        if owned_voice is None or owned_voice.user_id != user_id or owned_voice.state != "ready":
            raise ValueError(f"Unknown or not-ready voice_model_id={voice_model_id!r}")
        provider_name = owned_voice.provider
        provider_voice_id = owned_voice.provider_model_id
    else:
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
        voice_model_id=voice_model_id,
        input={
            "text": text,
            "voice_id": str(voice_id) if voice_id else None,
            "voice_model_id": str(voice_model_id) if voice_model_id else None,
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
    if provider_name == "fish_audio":
        # Which Fish Audio TTS model to use is an app_settings value (ADR
        # 0012), not a hardcoded constant in providers/fish_audio.py — read
        # fresh per-request (no caching), same as tts_credits_per_10_chars,
        # so bumping it to whatever Fish recommends next is a
        # PATCH /admin/settings/fish_tts_model, not a deploy. Only fetched
        # for this provider — Azure/Google have no equivalent concept, no
        # reason to pay the extra lookup on their requests.
        provider_inputs["model"] = await app_settings.get_setting(db, "fish_tts_model")
    job_ref: JobRef = await provider.submit("tts", provider_inputs)

    if job_ref.status == "succeeded":
        await _complete_success(db, job=job, credit_hold=credit_hold, job_ref=job_ref)
    elif job_ref.status == "failed":
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
    else:
        # None of the TTS-capable providers (Azure/Google/Fish Audio) ever
        # return pending/processing — this branch exists only because the
        # interface (ADR 0002) is shared with genuinely async providers
        # (Kie, later).
        job.status = job_ref.status
        job.provider_state = job_ref.provider_state

    # Commit explicitly here rather than relying solely on get_db()'s
    # post-yield commit: a client that immediately polls GET /jobs/{id} right
    # after this response must see the committed row, not a race against
    # request-teardown timing. (get_db()'s own commit becomes a harmless
    # no-op on top of this.)
    await db.commit()
    return job


async def submit_voice_model_training(
    db: AsyncSession,
    *,
    user_id: str,
    title: str,
    audio_bytes: bytes,
    audio_filename: str,
    reference_text: str | None = None,
) -> Job:
    """Submit a voice-cloning job (ADR 0009) — an ordinary job like `tts`,
    just with `capability="voice_model_training"` and a `voice_models` row
    as its success output instead of an `assets` row. Fish Audio only for
    now (the only provider this product has a verified cloning integration
    against — ADR 0009's own open item on Azure/Google is still open).

    **Free** (`estimated_cost=0`): the prior project never charged for
    training a clone either (only for *using* one to generate speech, at
    the ordinary per-character TTS rate) — this ports that verified,
    already-shipped pricing rather than inventing a number, and resolves
    ADR 0009's "exact credit cost of training" open item. Still goes
    through the normal hold->settle/release lifecycle at that $0 amount
    rather than skipping it, so training jobs get the same audit trail
    (credit_transactions rows) and no-charge-on-failure guarantee as
    every other capability, for free (pun intended).

    Fish Audio's `train_mode="fast"` (the only mode this adapter uses,
    `providers/fish_audio.py`) is synchronous — verified against the real
    API: the model is already `state: "trained"` in the same response that
    creates it, no polling needed. So this looks exactly like `submit_tts`'s
    shape: submit, get back an already-terminal `JobRef`, done."""
    estimated_cost = 0

    job = Job(
        user_id=user_id,
        capability="voice_model_training",
        provider="fish_audio",
        status="pending",
        input={"title": title, "reference_text": reference_text},
        estimated_cost=estimated_cost,
    )
    db.add(job)
    await db.flush()  # assigns job.id

    credit_hold = await credits.hold(db, user_id=user_id, job_id=job.id, amount=estimated_cost)
    job.hold_id = credit_hold.id

    provider = get_provider_by_name("fish_audio")
    job_ref: JobRef = await provider.submit(
        "voice_model_training",
        {
            "title": title,
            "audio_bytes": audio_bytes,
            "audio_filename": audio_filename,
            "reference_text": reference_text,
        },
    )

    if job_ref.status == "succeeded":
        output = job_ref.output or {}
        actual_cost = job.estimated_cost
        await credits.settle(db, credit_hold, actual_cost)

        voice_model = VoiceModel(
            user_id=user_id,
            title=title,
            provider="fish_audio",
            provider_model_id=output["provider_model_id"],
            state="ready" if output.get("state") == "trained" else "training",
            created_from_job_id=job.id,
        )
        db.add(voice_model)
        await db.flush()  # assigns voice_model.id

        job.status = "succeeded"
        job.actual_cost = actual_cost
        job.completed_at = datetime.now(UTC)
        job.voice_model_id = voice_model.id
        job.output = {"voice_model_id": str(voice_model.id)}
    elif job_ref.status == "failed":
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
    else:
        # Fast-mode training is synchronous (verified) — this branch exists
        # only for interface parity with ADR 0002's async-provider shape.
        job.status = job_ref.status
        job.provider_state = job_ref.provider_state

    # See submit_tts's comment above on why this commit is explicit.
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
