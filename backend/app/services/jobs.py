"""Orchestrates job submission and owns the hold -> settle/release lifecycle
(ADR 0002 + ADR 0003).

**Since ADR 0014**, "submit" and "execute" are two different functions,
called from two different places:
- `submit_tts()`/`submit_voice_model_training()` (called from `api/`) only
  create the `Job` row (as `pending`) and hold credits — they never call a
  provider themselves anymore, so a request handler calling these returns
  in milliseconds regardless of how long the vendor takes.
- `execute_tts_job()`/`execute_voice_model_training_job()` (called from
  `worker/dispatcher.py`, with a DB session the worker opened itself —
  never the request's) do what used to happen inline: call the provider,
  settle or release credits, write the terminal state.

This split is the whole point of ADR 0014 — see its "Context" for the two
concrete problems (DB-connection-pool exhaustion; Fish Audio's real
5-concurrent-request limit) that made the old inline shape not scale.

**Since ADR 0026**, the queue itself is the `jobs` table — a `pending` row
*is* the queue entry, picked up via `SELECT ... FOR UPDATE SKIP LOCKED`
(`worker/dispatcher.py`), woken up immediately via Postgres `NOTIFY`
(`core/pg_queue.py`) rather than arq/Redis polling. This module stays
queue-mechanism-agnostic either way — a `submit_*` function's job here ends
at "commit a pending row and notify," not "how does something eventually
run it."
"""

import base64
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import pg_queue
from app.core import queue as queue_service
from app.models.models import Asset, CreditHold, Job, VoiceModel
from app.providers.base import JobRef, JobStatus
from app.providers.registry import get_provider_by_name
from app.services import app_settings, credits
from app.services import assets as assets_service
from app.services import kie_catalog as kie_catalog_service
from app.services import voice_catalog as voice_catalog_service

logger = logging.getLogger(__name__)


async def publish_job_event(job: Job) -> None:
    """ADR 0018: the real-time half of "submit, then find out when it's
    done without polling" — called at every point a job reaches a terminal
    state (`_complete_success`, `_complete_kie_success`, `_complete_failure`,
    plus the two places that write a terminal state inline rather than
    through one of those: `execute_voice_model_training_job`'s own success
    path, and `worker/cron.py sweep_stuck_jobs`'s timeout path).

    Publishes to the owning user's own Redis pub/sub channel — `GET /events`
    (`api/routes_events.py`) subscribes per-connected-user and forwards each
    message to that one browser tab as an SSE event. This is Redis's one
    remaining job in this codebase (ADR 0026 moved the job queue itself to
    Postgres) — a plain `PUBLISH` via `queue_service`'s pool, nothing here
    for anything to pick up later, just a fire-and-forget signal to
    whoever happens to be listening right now.

    Best-effort and silent on failure: a dropped pub/sub message only costs
    the user a slightly-stale "processing" chip until they next reload
    (`GET /jobs` is always the real source of truth) — it must never affect
    the job's own already-committed outcome, so this never raises."""
    try:
        pool = await queue_service.get_pool()
        await pool.publish(
            f"job-events:{job.user_id}",
            json.dumps({"job_id": str(job.id), "status": job.status, "capability": job.capability}),
        )
    except Exception:
        logger.warning("Failed to publish job-event for job %s", job.id, exc_info=True)


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
    """Create a pending TTS job and hold credits (ADR 0014) — does not call
    a provider; see `execute_tts_job` for that. Raises
    credits.InsufficientCreditsError before anything is committed if the
    user can't afford the estimated cost; raises ValueError if
    voice_id/voice_model_id doesn't resolve to a real, owned voice.

    Which provider a job routes to is decided by the voice, not the
    capability — exactly one of two kinds of voice is given (schemas.TTSRequest
    enforces this with a model_validator, so this function trusts it's
    already true):
    - `voice_id`: a `voice_catalog` row, which carries its own provider
      (docs/data-model.md) — picking a voice IS picking a provider.
    - `voice_model_id`: a `voice_models` row (ADR 0009) — a voice the caller
      has cloned themselves. Currently always `provider="fish_audio"` (the
      only provider this slice's cloning is built against); the row must
      belong to `user_id` and be `state="ready"`, or this raises ValueError.
    Neither is optional at the HTTP layer — Fish Audio isn't a general "no
    voice selected" fallback, so there is no product-sensible default.

    Only `provider` is resolved here (which queue the job goes to); the
    full voice resolution (`provider_voice_id`/`locale`) and the
    speed/volume/pitch-to-provider-units conversion happen in
    `execute_tts_job`, once a worker actually picks the job up — re-reading
    `voice_catalog`/`voice_models` there rather than threading resolved
    values through the queue payload keeps that payload to just a job id."""
    estimated_cost = await credits.estimate_tts_cost(db, text)

    if voice_model_id is not None:
        owned_voice = await db.get(VoiceModel, voice_model_id)
        if owned_voice is None or owned_voice.user_id != user_id or owned_voice.state != "ready":
            raise ValueError(f"Unknown or not-ready voice_model_id={voice_model_id!r}")
        provider_name = owned_voice.provider
    else:
        voice = await voice_catalog_service.get_voice(db, voice_id)
        if voice is None:
            raise ValueError(f"Unknown voice_id={voice_id!r}")
        provider_name = voice.provider

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
    await db.commit()

    await pg_queue.notify_job_ready(db)
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
    """Create a pending voice-cloning job (ADR 0009) and hold (0) credits —
    same split as `submit_tts`, see `execute_voice_model_training_job` for
    the part that actually calls Fish Audio.

    Fish Audio only for now (the only provider this product has a verified
    cloning integration against — ADR 0009's own open item on Azure/Google
    is still open). **Free** (`estimated_cost=0`): the prior project never
    charged for training a clone either (only for *using* one to generate
    speech, at the ordinary per-character TTS rate) — this ports that
    verified, already-shipped pricing rather than inventing a number, and
    resolves ADR 0009's "exact credit cost of training" open item. Still
    goes through the normal hold->settle/release lifecycle at that $0
    amount rather than skipping it, so training jobs get the same audit
    trail (credit_transactions rows) and no-charge-on-failure guarantee as
    every other capability, for free (pun intended).

    **Since ADR 0026**: the audio is base64-encoded straight into `job.input`
    (JSONB) rather than passed through a queue payload — there's no queue
    payload anymore, a `pending` row is the only thing that exists between
    submission and pickup. Base64 costs ~33% size overhead, accepted as
    trivial at the 15MB cap `routes_voice_models.py` already enforces
    (~20MB stored, nowhere near a real Postgres/JSONB size concern)."""
    estimated_cost = 0

    job = Job(
        user_id=user_id,
        capability="voice_model_training",
        provider="fish_audio",
        status="pending",
        input={
            "title": title,
            "reference_text": reference_text,
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
            "audio_filename": audio_filename,
        },
        estimated_cost=estimated_cost,
    )
    db.add(job)
    await db.flush()  # assigns job.id

    credit_hold = await credits.hold(db, user_id=user_id, job_id=job.id, amount=estimated_cost)
    job.hold_id = credit_hold.id
    await db.commit()

    await pg_queue.notify_job_ready(db)
    return job


async def submit_kie_job(
    db: AsyncSession,
    *,
    user_id: str,
    model_id: str,
    inputs: dict[str, Any],
    uploaded_r2_keys: list[str] | None = None,
    visibility: str = "private",
) -> Job:
    """Create a pending Kie job and hold credits — the *submit-only* work
    (ADR 0014/0015) happens later, once a worker claims this row and calls
    `execute_kie_submit_job`, which only ever calls Kie's createTask and
    returns; it never waits for Kie to actually finish (that's the whole
    point of splitting "submit" from "track to completion" — see
    `execute_kie_submit_job`/`finalize_kie_job` and architecture.md §3f).

    Category-agnostic by construction: `capability` is set from the model's
    own `category_id` (e.g. "text-to-image"), not a fixed enum member —
    a new Kie category needs no change here, only a new `kie_categories`/
    `kie_models` row (ADR 0015).

    `uploaded_r2_keys` (ADR 0016): an image-to-image job's `inputs` already
    contains real, live URLs (from `POST /kie/uploads`, called by the
    frontend before this) — these are the matching R2 keys, tracked here
    only so `cleanup_kie_uploads` can delete them once this job reaches a
    terminal state. Empty for a text-to-image job.

    `provider_model_id`/`fixed_inputs` (ADR 0017): `model_id` is our own
    catalog's id, not always what's literally sent to Kie (Veo 3.1's three
    quality tiers are all really `provider_model_id="veo-3-1"`) — resolved
    once here and stored alongside the merged `inputs` so
    `execute_kie_submit_job` never needs to touch the catalog again, same
    as the rest of this function's fields."""
    kie_model = await kie_catalog_service.get_model(db, model_id)
    if kie_model is None or not kie_model.enabled:
        raise ValueError(f"Unknown or disabled Kie model_id={model_id!r}")
    estimated_cost = kie_catalog_service.estimate_cost(kie_model, inputs)
    merged_inputs = {**inputs, **kie_model.fixed_inputs}

    job = Job(
        user_id=user_id,
        capability=kie_model.category_id,
        provider="kie",
        model_id=model_id,
        status="pending",
        input={
            "model_id": model_id,
            "provider_model_id": kie_model.provider_model_id,
            "inputs": merged_inputs,
            "uploaded_r2_keys": uploaded_r2_keys or [],
        },
        estimated_cost=estimated_cost,
        visibility=visibility if visibility == "public" else "private",
    )
    db.add(job)
    await db.flush()  # assigns job.id

    credit_hold = await credits.hold(db, user_id=user_id, job_id=job.id, amount=estimated_cost)
    job.hold_id = credit_hold.id
    await db.commit()

    await pg_queue.notify_job_ready(db)
    return job


async def cleanup_kie_uploads(job: Job) -> None:
    """Deletes a Kie image-to-image job's short-lived public reference-image
    upload(s) (ADR 0016) — called at every point a Kie job reaches a
    terminal outcome (including failing to even enqueue), success or
    failure alike. Best-effort: a cleanup failure is logged, never raised —
    it must not affect the job's own outcome, same posture as Fish Audio's
    best-effort voice-model delete (`services/voice_models.py`)."""
    r2_keys = job.input.get("uploaded_r2_keys") if isinstance(job.input, dict) else None
    if not r2_keys:
        return
    for r2_key in r2_keys:
        try:
            await assets_service.delete_object(r2_key)
        except Exception:
            logger.warning("Failed to clean up Kie upload %s", r2_key, exc_info=True)


class TransientProviderError(Exception):
    """Raised by `execute_*_job` instead of writing a final `failed` state,
    when a provider call failed in a way that looks transient (a network
    timeout, connection error, or 5xx — see `_is_transient_error`) and
    retries remain. `worker/dispatcher.py` catches this, increments
    `job.tries`, and reschedules the row (`status` back to `pending`,
    `run_after` set to a backoff delay) — the direct replacement for arq's
    own `Retry`, which is what this exception mapped to before ADR 0026.
    This module stays queue-mechanism-agnostic either way."""


def _is_transient_error(error: str | None) -> bool:
    """Every provider adapter's `JobRef.error` follows one of two shapes
    (verified by inspection, all three adapters use the same wording):
    `"{Provider} request failed: {exc}"` for a network-level failure with
    no HTTP response at all (timeout, connection refused) — always
    transient; or `"{Provider} {status_code}: {body}"` for a real HTTP
    error response — transient only if it's a 5xx (server-side), never a
    4xx (a definitive rejection: bad input, unsupported voice, etc. — retrying
    would just fail the same way again while wasting a vendor call)."""
    if not error:
        return False
    if "request failed:" in error:
        return True
    match = re.search(r"\b(\d{3}):", error)
    return bool(match) and match.group(1).startswith("5")


# How many total attempts (first try + retries) a transient provider failure
# gets before it's written as a final `failed` — matched by
# `worker/dispatcher.py`'s own reschedule-vs-give-up check.
MAX_PROVIDER_TRIES = 3


async def execute_tts_job(
    db: AsyncSession, job_id: uuid.UUID, *, job_try: int = 1
) -> Job | None:
    """The part of TTS submission that used to run inline before ADR 0014:
    resolve the voice again from the job's own stored `input`, call the
    provider, settle or release credits, write the terminal state. Called
    by the dispatcher (`worker/dispatcher.py`) with its own DB session,
    after already claiming the row (`status` is already `processing` by
    the time this runs — the claim step owns that transition, ADR 0026).

    Returns `None` if the job or its hold has vanished by the time a worker
    picks it up — shouldn't happen in practice (nothing deletes a pending
    job), but a missing row is a no-op here, not a crash.

    Raises `TransientProviderError` (instead of writing a final `failed`
    state) when the provider call looks like a transient failure and
    `job_try` hasn't reached `MAX_PROVIDER_TRIES` yet — see
    `_is_transient_error`'s docstring for what counts. The job is left in
    `processing` in that case, credits still held, for the dispatcher's
    retry-reschedule to pick back up.

    The terminal-status check below used to be load-bearing under arq
    (ADR 0014): arq's delivery guarantee was *at-least-once*, and a real
    worker crash — between this function's own commit and arq separately
    acknowledging the task in Redis — really did redeliver an
    already-succeeded job once (`backend/README.md`), calling a vendor a
    second time for real. **Under ADR 0026's `SELECT ... FOR UPDATE SKIP
    LOCKED` claim, that specific failure mode is gone** — a row can't be
    claimed again once it's no longer `pending`, by this or any other
    dispatcher process, so nothing re-delivers an already-terminal job the
    way arq's own bookkeeping could. This check is kept anyway as cheap,
    still-correct defensive insurance (it costs one extra `if`), not
    because a live path to trigger it is known to still exist."""
    job = await db.get(Job, job_id)
    if job is None:
        return None
    if job.status in ("succeeded", "failed"):
        logger.warning("execute_tts_job: job %s already %s, skipping redelivery", job_id, job.status)
        return job
    credit_hold = await db.get(CreditHold, job.hold_id) if job.hold_id else None
    if credit_hold is None:
        return None

    text = job.input["text"]
    speed = job.input.get("speed", 1.0)
    volume = job.input.get("volume", 50)
    pitch = job.input.get("pitch", 50)
    voice_id_str = job.input.get("voice_id")
    voice_model_id_str = job.input.get("voice_model_id")

    locale: str | None = None
    if voice_model_id_str:
        owned_voice = await db.get(VoiceModel, uuid.UUID(voice_model_id_str))
        if owned_voice is None or owned_voice.user_id != job.user_id or owned_voice.state != "ready":
            await _complete_failure(
                db, job=job, credit_hold=credit_hold, error="Voice is no longer available."
            )
            await db.commit()
            return job
        provider_voice_id = owned_voice.provider_model_id
    else:
        voice = await voice_catalog_service.get_voice(db, uuid.UUID(voice_id_str))
        if voice is None:
            await _complete_failure(
                db, job=job, credit_hold=credit_hold, error="Voice is no longer available."
            )
            await db.commit()
            return job
        provider_voice_id = voice.provider_voice_id
        locale = voice.locale

    provider = get_provider_by_name(job.provider)
    provider_inputs: dict[str, Any] = {
        "text": text,
        "speed": speed,
        "volume": volume,
        "pitch": pitch,
        "provider_voice_id": provider_voice_id,
        "locale": locale,
    }
    if job.provider == "fish_audio":
        # See providers/fish_audio.py's docstring — read fresh per attempt
        # (no caching), same as tts_credits_per_10_chars (ADR 0012).
        provider_inputs["model"] = await app_settings.get_setting(db, "fish_tts_model")

    job_ref: JobRef = await provider.submit("tts", provider_inputs)

    if job_ref.status == "succeeded":
        await _complete_success(db, job=job, credit_hold=credit_hold, job_ref=job_ref)
    elif job_ref.status == "failed":
        if job_try < MAX_PROVIDER_TRIES and _is_transient_error(job_ref.error):
            await db.commit()  # job stays "processing", hold stays active
            raise TransientProviderError(job_ref.error)
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
    else:
        # None of the TTS-capable providers (Azure/Google/Fish Audio) ever
        # return pending/processing — this branch exists only because the
        # interface (ADR 0002) is shared with genuinely async providers
        # (Kie, later).
        job.status = job_ref.status
        job.provider_state = job_ref.provider_state

    await db.commit()
    return job


async def execute_voice_model_training_job(
    db: AsyncSession, job_id: uuid.UUID, *, job_try: int = 1
) -> Job | None:
    """The part of voice-cloning submission that used to run inline before
    ADR 0014 — same shape as `execute_tts_job`, for `voice_model_training`.

    Fish Audio's `train_mode="fast"` (the only mode this adapter uses,
    `providers/fish_audio.py`) is synchronous — verified against the real
    API: the model is already `state: "trained"` in the same response that
    creates it, no separate polling step needed here.

    **Since ADR 0026**: no longer takes `audio_bytes`/`audio_filename` as
    parameters — there's no queue payload to carry them in anymore, so
    `submit_voice_model_training` base64-encodes the audio straight into
    `job.input`, and this function decodes it back out, same "everything
    needed to execute lives on the row" shape `execute_tts_job` already had.

    Terminal-status guard: see `execute_tts_job`'s docstring — kept as
    defensive insurance, though ADR 0026's `SKIP LOCKED` claim removes the
    specific arq-redelivery path that used to make this load-bearing."""
    job = await db.get(Job, job_id)
    if job is None:
        return None
    if job.status in ("succeeded", "failed"):
        logger.warning(
            "execute_voice_model_training_job: job %s already %s, skipping redelivery",
            job_id, job.status,
        )
        return job
    credit_hold = await db.get(CreditHold, job.hold_id) if job.hold_id else None
    if credit_hold is None:
        return None

    title = job.input["title"]
    reference_text = job.input.get("reference_text")
    audio_bytes = base64.b64decode(job.input["audio_b64"])
    audio_filename = job.input["audio_filename"]

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
            user_id=job.user_id,
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
        # The base64 sample was only ever needed to reach this point — drop
        # it now rather than let a ~20MB-ish blob sit in every completed
        # training job's row forever (reassigned, not mutated in place, so
        # SQLAlchemy's change tracking actually notices the JSONB update).
        job.input = {k: v for k, v in job.input.items() if k != "audio_b64"}
        await publish_job_event(job)
    elif job_ref.status == "failed":
        if job_try < MAX_PROVIDER_TRIES and _is_transient_error(job_ref.error):
            await db.commit()
            raise TransientProviderError(job_ref.error)
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
        job.input = {k: v for k, v in job.input.items() if k != "audio_b64"}
    else:
        # Fast-mode training is synchronous (verified) — this branch exists
        # only for interface parity with ADR 0002's async-provider shape.
        job.status = job_ref.status
        job.provider_state = job_ref.provider_state

    await db.commit()
    return job


async def execute_kie_submit_job(
    db: AsyncSession, job_id: uuid.UUID, *, job_try: int = 1
) -> Job | None:
    """ADR 0014/0015's `queue:kie-submit` task: call Kie's createTask
    *only*, store `provider_job_id`, leave the job `processing` — it never
    waits for Kie to actually finish. Completion is a separate concern
    entirely (the webhook or the poll-sweep cron both call
    `finalize_kie_job`, never this function again).

    Terminal-status guard doesn't fit here the way it does in the other
    `execute_*` functions — this one's own *normal* outcome is `processing`,
    not terminal. The real redelivery signal is `provider_job_id` already
    being set: that's this function's one real side effect (an actual
    `createTask` call), so once it exists there is nothing left for a
    redelivered attempt to safely do. Live-caught under arq (ADR 0014), not
    hypothetical: a worker crash between this function's commit and arq's
    own delivery acknowledgment redelivered an already-submitted job, which
    without this guard created a second real Kie video generation and
    clobbered the first one's `provider_job_id` in the DB. **ADR 0026's
    `SKIP LOCKED` claim removes that specific arq-redelivery path** (see
    `execute_tts_job`'s docstring) — this check stays as defensive
    insurance, same reasoning as there."""
    job = await db.get(Job, job_id)
    if job is None:
        return None
    if job.provider_job_id is not None:
        logger.warning(
            "execute_kie_submit_job: job %s already has provider_job_id=%s, skipping redelivery",
            job_id, job.provider_job_id,
        )
        return job
    credit_hold = await db.get(CreditHold, job.hold_id) if job.hold_id else None
    if credit_hold is None:
        return None

    # ADR 0017: `provider_model_id` (what Kie itself calls it) can differ
    # from `model_id` (our own catalog id) — always the former for the
    # actual call. `inputs` already has any `fixed_inputs` merged in
    # (submit_kie_job, above), so this needs no catalog lookup here.
    provider_model_id = job.input["provider_model_id"]
    inputs = job.input["inputs"]

    provider = get_provider_by_name("kie")
    job_ref: JobRef = await provider.submit(
        job.capability, {"model_id": provider_model_id, "input": inputs}
    )

    if job_ref.status == "failed":
        if job_try < MAX_PROVIDER_TRIES and _is_transient_error(job_ref.error):
            await db.commit()  # job stays "processing", hold stays active
            raise TransientProviderError(job_ref.error)
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_ref.error)
        await cleanup_kie_uploads(job)  # ADR 0016 — terminal, no retry left
    else:
        # Always true in practice — providers/kie.py's submit() never
        # returns "succeeded" — but written generically rather than assuming,
        # in case a future Kie-style vendor's create-task call can itself be
        # instantly terminal for some inputs.
        job.provider_job_id = job_ref.provider_job_id
        job.provider_state = job_ref.provider_state
        if job_ref.status == "succeeded":
            await _complete_kie_success(
                db, job=job, credit_hold=credit_hold, job_status=_as_job_status(job_ref)
            )
            await cleanup_kie_uploads(job)  # ADR 0016

    await db.commit()
    return job


def _as_job_status(job_ref: JobRef) -> JobStatus:
    return JobStatus(
        status=job_ref.status, provider_state=job_ref.provider_state, output=job_ref.output
    )


async def finalize_kie_job(db: AsyncSession, job_id: uuid.UUID, job_status: JobStatus) -> Job | None:
    """The one place a Kie job's `JobStatus` (from `providers/kie.py`'s
    `poll()`) is applied to the DB — called two ways (ADR 0015): the webhook
    (`POST /webhooks/kie`, primary path) and the poll-sweep cron
    (`worker/cron.py`, fallback), both re-deriving the same `JobStatus` via
    `poll()` rather than trusting a webhook body's own payload, so there's
    exactly one code path for "what does a terminal Kie job look like."

    `SELECT ... FOR UPDATE` on the hold row is what makes it safe for both
    paths to race on the same job: the second to arrive blocks on the lock,
    then sees the hold already resolved and no-ops, instead of double-
    settling credits."""
    job = await db.get(Job, job_id)
    if job is None:
        return None
    if job.hold_id is None:
        return job
    credit_hold = (
        await db.execute(select(CreditHold).where(CreditHold.id == job.hold_id).with_for_update())
    ).scalar_one_or_none()
    if credit_hold is None or credit_hold.status != "active":
        return job  # already resolved by the other completion path

    if job_status.status == "succeeded":
        await _complete_kie_success(db, job=job, credit_hold=credit_hold, job_status=job_status)
        await cleanup_kie_uploads(job)  # ADR 0016
    elif job_status.status == "failed":
        await _complete_failure(db, job=job, credit_hold=credit_hold, error=job_status.error)
        await cleanup_kie_uploads(job)  # ADR 0016
    else:
        job.provider_state = job_status.provider_state

    await db.commit()
    return job


# content-type -> file extension, for the handful of media types Kie's
# image models return. Falls back to "bin" rather than guessing wrong.
_EXTENSION_BY_CONTENT_TYPE: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/mpeg": "mp3",
}


async def _download(url: str) -> tuple[bytes, str]:
    """Kie's result URLs expire ~24h after completion (architecture.md
    §3d) — downloaded here and handed to `assets_service.upload_bytes`
    (already capability-agnostic: it just puts bytes at a job-namespaced R2
    key) to mirror into R2 before that window closes."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.content, response.headers.get("content-type", "application/octet-stream")


async def _complete_kie_success(
    db: AsyncSession, *, job: Job, credit_hold: CreditHold, job_status: JobStatus
) -> None:
    """Settles from Kie's own `creditsConsumed`, 1:1 — not this catalog's
    `estimate_cost()`, which only ever produces the up-front hold amount
    (ADR 0015). Falls back to the estimate only if Kie ever omits it."""
    output = job_status.output or {}
    result_urls: list[str] = output.get("result_urls") or []
    credits_consumed = output.get("credits_consumed")
    actual_cost = int(credits_consumed) if credits_consumed is not None else job.estimated_cost
    await credits.settle(db, credit_hold, actual_cost)

    asset_fields: dict[str, Any] = {}
    if result_urls:
        media_bytes, content_type = await _download(result_urls[0])
        extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
        asset_fields = await assets_service.upload_bytes(
            job_id=job.id, data=media_bytes, content_type=content_type, extension=extension
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
    job.provider_state = job_status.provider_state
    asset_url = f"/jobs/{job.id}/asset" if asset_fields else None
    job.output = {"asset_url": asset_url}
    await publish_job_event(job)


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
    await publish_job_event(job)


async def _complete_failure(
    db: AsyncSession, *, job: Job, credit_hold: CreditHold, error: str | None
) -> None:
    await credits.release(db, credit_hold)
    job.status = "failed"
    job.error = error
    job.completed_at = datetime.now(UTC)
    await publish_job_event(job)


async def get_job(db: AsyncSession, job_id: uuid.UUID, *, user_id: str) -> Job | None:
    """Read a job's current state. Since ADR 0014, `pending`/`processing`
    are real states a client can observe while polling — the provider call
    happens in a worker, not inline in the submitting request anymore."""
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
