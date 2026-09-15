"""arq cron jobs (ADR 0014) — periodic, non-request-triggered work, run by
a dedicated worker process (`CronWorker` below) so a cron tick never
competes with a provider queue's own `max_jobs` for concurrency (see
`docs/architecture.md` §3f — this is also what resolves ADR 0007's
previously-open "scheduling mechanism" question).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from arq import cron
from sqlalchemy import select

from app.core.db import async_session_factory
from app.core.queue import redis_settings
from app.models.models import CreditHold, Job
from app.providers.registry import get_provider_by_name
from app.services import credits, jobs

logger = logging.getLogger(__name__)

# A job sitting pending/processing this long almost certainly means its
# worker crashed mid-task or the job was never picked up at all (e.g. no
# worker process was running for its queue) — every real provider call this
# codebase makes today finishes in seconds. Reuses Kie's own documented
# 10-15 minute polling-timeout figure (architecture.md §3d) as a starting
# point; not tuned against real data yet — ADR 0007's own open item.
_STUCK_JOB_TIMEOUT = timedelta(minutes=15)


async def sweep_stuck_jobs(ctx: dict[str, Any]) -> int:
    """ADR 0007's "stuck-job sweep", implemented as an arq cron job now that
    arq is this project's scheduling mechanism (ADR 0014's resolution of
    ADR 0007's open item). One batched pass over every stuck row — never a
    per-job wait, so this stays cheap to run frequently regardless of how
    many jobs happen to be stuck."""
    cutoff = datetime.now(UTC) - _STUCK_JOB_TIMEOUT
    swept = 0
    async with async_session_factory() as db:
        stuck_jobs = (
            await db.execute(
                select(Job).where(Job.status.in_(["pending", "processing"]), Job.updated_at < cutoff)
            )
        ).scalars().all()
        for job in stuck_jobs:
            credit_hold = await db.get(CreditHold, job.hold_id) if job.hold_id else None
            if credit_hold is not None and credit_hold.status == "active":
                await credits.release(db, credit_hold)
            job.status = "failed"
            job.error = "Timed out waiting for the provider (stuck-job sweep)."
            job.completed_at = datetime.now(UTC)
            if job.provider == "kie":
                await jobs.cleanup_kie_uploads(job)  # ADR 0016
            await jobs.publish_job_event(job)  # ADR 0018 — this bypasses _complete_failure
            swept += 1
        if swept:
            await db.commit()
    if swept:
        logger.warning("Stuck-job sweep resolved %d job(s) to failed", swept)
    return swept


async def sweep_kie_processing_jobs(ctx: dict[str, Any]) -> int:
    """ADR 0015's poll-based fallback for Kie completion — the webhook
    (`POST /webhooks/kie`) is the primary path; this catches anything it
    missed (callback never arrived, or arrived before this backend had a
    public URL configured) by batch-polling Kie's `recordInfo` for every
    Kie job still `processing`. Runs every minute — frequent enough that a
    missed webhook rarely costs a user more than ~1 minute of extra wait,
    but still a batched pass, never a per-job wait (`sweep_stuck_jobs`
    above, at 15 minutes, remains the final backstop if even this sweep's
    own poll calls fail outright, e.g. a Kie outage)."""
    resolved = 0
    async with async_session_factory() as db:
        stuck_jobs = (
            await db.execute(
                select(Job).where(
                    Job.provider == "kie",
                    Job.status == "processing",
                    Job.provider_job_id.is_not(None),
                )
            )
        ).scalars().all()
        if not stuck_jobs:
            return 0
        provider = get_provider_by_name("kie")
        for job in stuck_jobs:
            job_status = await provider.poll(job.provider_job_id)
            if job_status.status in ("succeeded", "failed"):
                resolved += 1
            await jobs.finalize_kie_job(db, job.id, job_status)
    if resolved:
        logger.info("Kie poll-sweep resolved %d job(s)", resolved)
    return resolved


class CronWorker:
    """No `functions` of its own to consume from a provider queue — this
    process exists only to tick cron jobs on a timer, run as:
    `arq app.worker.cron.CronWorker`."""

    functions: ClassVar[list] = []
    cron_jobs: ClassVar[list] = [
        cron(sweep_stuck_jobs, minute=set(range(0, 60, 5))),  # every 5 min
        cron(sweep_kie_processing_jobs, minute=set(range(60))),  # every 1 min
    ]
    queue_name = "queue:cron"
    redis_settings = redis_settings()
