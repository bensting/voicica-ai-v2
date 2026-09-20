"""The job dispatcher (ADR 0026) — replaces arq/Redis entirely for queue
dispatch. A `jobs` row with `status='pending'` *is* the queue entry; this
process claims a batch via `SELECT ... FOR UPDATE SKIP LOCKED` (the same
idempotency idiom already used everywhere else in this codebase for "two
things racing on one row must not double-process it" — `finalize_kie_job`,
`billing.complete_purchase`), runs each job, and reschedules or finalizes
it. Woken up immediately by a Postgres `NOTIFY` (`core/pg_queue.py`) the
instant a new job is submitted, with a coarse fallback poll as the safety
net for a missed notification — the same "push primary, poll fallback"
shape Kie's own webhook + poll-sweep cron already uses (ADR 0015).

Run as: python -m app.worker.dispatcher
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.db import async_session_factory
from app.core.pg_queue import listen_for_jobs
from app.services import jobs
from app.worker.cron import sweep_kie_processing_jobs, sweep_stuck_jobs

logger = logging.getLogger(__name__)

# How long to wait for a NOTIFY before claiming anyway — the safety net for
# a missed notification (a race between commit and LISTEN registration, a
# brief connection drop). Not the primary trigger, NOTIFY is, so this can
# stay generous without hurting real pickup latency.
_FALLBACK_POLL_SECONDS = 20.0

# How many pending rows to claim per pass — generous, since the real
# concurrency limit is enforced per-provider below, not by this number.
_CLAIM_BATCH_SIZE = 20

# Backoff between retries of a transient provider failure: try 2 is
# delayed 5s, try 3 is delayed 10s, etc. — matches worker/tasks.py's old
# arq-era constant of the same name/value.
_RETRY_BACKOFF_SECONDS = 5

# Matches ADR 0014's old arq `WorkerSettings.job_timeout` — see that
# module's own retired comment for the 60s-provider-call + 180s-R2-upload
# math this covers; unchanged by moving off arq.
_JOB_TIMEOUT_SECONDS = 300

# Fish Audio's real, observed hard limit (`ratelimit-limit-concurrency: 5`
# in its own response headers, backend/README.md) — one seat of headroom.
# Azure/Google/Kie-submit have no observed real limit (ADR 0014's own
# caveat, carried over unchanged) — generous caps to bound chaos, not
# measured ceilings. In-process `asyncio.Semaphore`s, not Redis — this is
# exactly the mechanism arq's own `max_jobs` used internally per queue
# (verified by reading arq's source, `arq/worker.py`); the only thing that
# changes is scoping it per-provider ourselves inside one shared process
# instead of getting it "for free" from five separate queues/processes.
_SEMAPHORES: dict[str, asyncio.Semaphore] = {
    "fish_audio": asyncio.Semaphore(4),
    "azure": asyncio.Semaphore(20),
    "google": asyncio.Semaphore(20),
    "kie": asyncio.Semaphore(10),
}

_CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'processing'
    WHERE id IN (
        SELECT id FROM jobs
        WHERE status = 'pending' AND (run_after IS NULL OR run_after <= now())
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT :limit
    )
    RETURNING id, capability, provider
    """
)

_RESCHEDULE_SQL = text(
    "UPDATE jobs SET status = 'pending', tries = :tries, run_after = :run_after WHERE id = :id"
)


async def _claim_batch() -> list[tuple[uuid.UUID, str, str]]:
    async with async_session_factory() as db:
        result = await db.execute(_CLAIM_SQL, {"limit": _CLAIM_BATCH_SIZE})
        rows = result.fetchall()
        await db.commit()
        return [(r.id, r.capability, r.provider) for r in rows]


async def _reschedule(job_id: uuid.UUID, job_try: int) -> None:
    """The direct replacement for arq's `Retry(defer=...)` — `worker/
    tasks.py`'s old catch of `TransientProviderError`. Sets the row back to
    `pending` with `run_after` in the future; the fallback poll (or a
    coincidental NOTIFY from an unrelated new submission) picks it back up
    once due — nothing NOTIFYs specifically for a due retry, since nothing
    is watching wall-clock time to know when that is except the dispatcher
    itself, which polls anyway."""
    delay = _RETRY_BACKOFF_SECONDS * job_try
    async with async_session_factory() as db:
        await db.execute(
            _RESCHEDULE_SQL,
            {"tries": job_try, "run_after": datetime.now(UTC) + timedelta(seconds=delay), "id": job_id},
        )
        await db.commit()


async def _execute(job_id: uuid.UUID, capability: str, job_try: int) -> None:
    async with async_session_factory() as db:
        if capability == "voice_model_training":
            await jobs.execute_voice_model_training_job(db, job_id, job_try=job_try)
        elif capability != "tts":
            # Everything that isn't tts/voice_model_training is a Kie
            # category (text-to-image, image-to-video, ...) — capability
            # is set from `kie_categories.id`, open-ended by design (ADR
            # 0015), so this is "not one of the two named ones" rather than
            # an exhaustive enum check.
            await jobs.execute_kie_submit_job(db, job_id, job_try=job_try)
        else:
            await jobs.execute_tts_job(db, job_id, job_try=job_try)


async def _run_one(job_id: uuid.UUID, capability: str, provider: str) -> None:
    """Runs one already-claimed job under its provider's concurrency limit.
    A job can sit `processing` for a little while waiting on its semaphore
    before the real provider call even starts — acceptable: the stuck-job
    sweep's 15-minute window (ADR 0007) has enormous headroom over any
    realistic semaphore wait at this scale."""
    sem = _SEMAPHORES.get(provider)
    if sem is not None:
        async with sem:
            await _run_one_unlimited(job_id, capability)
    else:
        await _run_one_unlimited(job_id, capability)


async def _run_one_unlimited(job_id: uuid.UUID, capability: str) -> None:
    async with async_session_factory() as db:
        job = await db.get(jobs.Job, job_id)
    job_try = (job.tries if job else 0) + 1

    try:
        await asyncio.wait_for(_execute(job_id, capability, job_try), timeout=_JOB_TIMEOUT_SECONDS)
    except jobs.TransientProviderError:
        await _reschedule(job_id, job_try)
    except TimeoutError:
        # Matches ADR 0014's own documented arq behavior: don't touch the
        # row on a timeout — leave it `processing`, hold still active — the
        # stuck-job sweep is the real backstop for this, not a special case
        # here (a run that exhausts this timeout is rare and worth
        # investigating, not silently retried into the same wall).
        logger.warning("Job %s timed out after %ss", job_id, _JOB_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("Unhandled error running job %s", job_id)


async def _sweep_loop(name: str, fn, interval_seconds: float) -> None:
    """Plain timer loop — no Redis, no LISTEN, because these were never
    "wake on a new job" work in the first place, they're "wake on the
    clock regardless" (a stuck-job check, a Kie poll-sweep). That's exactly
    the kind of scheduling `LISTEN`/`NOTIFY` can't express (there's no
    event to wait for), same reason arq's own queue used polling
    internally (ADR 0026) — the difference here is this loop was always
    going to be a timer, on any architecture."""
    while True:
        try:
            await fn({})
        except Exception:
            logger.exception("%s sweep failed", name)
        await asyncio.sleep(interval_seconds)


async def run_forever() -> None:
    logger.info("Dispatcher starting (ADR 0026 — Postgres-native queue, no Redis for dispatch)")
    running: set[asyncio.Task] = set()

    async def claim_and_dispatch() -> None:
        for job_id, capability, provider in await _claim_batch():
            task = asyncio.create_task(_run_one(job_id, capability, provider))
            running.add(task)
            task.add_done_callback(running.discard)

    # Held in the same `running` set as claimed jobs — not because anything
    # here reads it back out, but because an `asyncio.Task` with no
    # remaining reference is fair game for garbage collection mid-run
    # (a real asyncio footgun, not just a lint nit); these two must live
    # for the whole process, so they get a durable reference like everything
    # else in this set does.
    running.add(asyncio.create_task(_sweep_loop("stuck-job", sweep_stuck_jobs, 300)))
    running.add(asyncio.create_task(_sweep_loop("kie-poll", sweep_kie_processing_jobs, 60)))

    async with listen_for_jobs() as notified:
        await claim_and_dispatch()  # catch up on anything already pending at startup
        while True:
            try:
                await asyncio.wait_for(notified.wait(), timeout=_FALLBACK_POLL_SECONDS)
                logger.info("Woken by NOTIFY")
            except TimeoutError:
                logger.info("Woken by fallback poll timeout")
            notified.clear()
            await claim_and_dispatch()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
