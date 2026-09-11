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
from app.providers.registry import get_provider
from app.services import assets as assets_service
from app.services import credits


async def submit_tts(
    db: AsyncSession, *, user_id: str, text: str, reference_id: str | None
) -> Job:
    """Submit a TTS job. Raises credits.InsufficientCreditsError before
    anything reaches a provider if the user can't afford the estimated cost."""
    estimated_cost = await credits.estimate_tts_cost(db, text)

    job = Job(
        user_id=user_id,
        capability="tts",
        provider="fish_audio",
        status="pending",
        input={"text": text, "reference_id": reference_id},
        estimated_cost=estimated_cost,
    )
    db.add(job)
    await db.flush()  # assigns job.id

    credit_hold = await credits.hold(db, user_id=user_id, job_id=job.id, amount=estimated_cost)
    job.hold_id = credit_hold.id

    provider = get_provider("tts")
    job_ref: JobRef = await provider.submit("tts", {"text": text, "reference_id": reference_id})

    if job_ref.status == "succeeded":
        await _complete_success(db, job=job, credit_hold=credit_hold, job_ref=job_ref)
    elif job_ref.status == "failed":
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
    else:
        # Fish Audio never returns pending/processing — this branch exists because
        # the interface (ADR 0002) is shared with async providers (Kie, later).
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
    job.output = {"asset_url": asset_url, "reference_id": output.get("reference_id")}


async def _complete_failure(
    db: AsyncSession, *, job: Job, credit_hold: CreditHold, error: str | None
) -> None:
    await credits.release(db, credit_hold)
    job.status = "failed"
    job.error = error
    job.completed_at = datetime.now(UTC)


async def get_job(db: AsyncSession, job_id: uuid.UUID, *, user_id: str) -> Job | None:
    """Read a job's current state. For this slice every job is already
    terminal by the time it's written (Fish Audio is synchronous) — there's
    nothing to poll yet. An async provider's poll would call `provider.poll()`
    here and advance the row before returning it; not needed until Kie."""
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        return None
    return job


async def get_job_with_asset(db: AsyncSession, job_id: uuid.UUID, *, user_id: str) -> Job | None:
    """Same as `get_job`, but with `.asset` eagerly loaded (selectinload) —
    for `GET /jobs/{id}/asset`, which needs the R2 key. `db.get()`'s default
    lazy relationship access isn't awaitable outside an explicit loader in an
    async session, hence the separate query shape rather than reusing `get_job`."""
    job = (
        await db.execute(select(Job).options(selectinload(Job.asset)).where(Job.id == job_id))
    ).scalar_one_or_none()
    if job is None or job.user_id != user_id:
        return None
    return job
