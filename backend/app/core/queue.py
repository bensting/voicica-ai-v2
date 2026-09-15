"""The one place `services/` reaches to hand work to a background worker
(ADR 0014) — an arq-backed Redis queue, split per provider so a slow or
rate-limited one (Kie; Fish Audio's real, observed 5-concurrent-request
limit) can never consume capacity a different provider's jobs need.

`services/jobs.py` calls `enqueue()` here instead of awaiting a provider
directly; `worker/settings.py` defines one `WorkerSettings` per queue name
below, each run as its own `arq` process with its own concurrency (`max_jobs`)
tuned to that provider's real limits.
"""

from typing import Any

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings

# Provider -> the queue its jobs are enqueued into. Fish Audio, Azure, and
# Google each get their own queue (and therefore their own worker
# concurrency ceiling) so one provider being slow/rate-limited never delays
# another's jobs, which a single shared queue would allow. "kie" (ADR 0015)
# only ever holds the short "create the task at Kie" step (worker/tasks.py's
# run_kie_submit_job) — see ADR 0014 and architecture.md §3f for why that's
# never a wait for Kie to finish generating.
QUEUE_NAMES: dict[str, str] = {
    "fish_audio": "queue:fish_audio",
    "azure": "queue:azure",
    "google": "queue:google",
    "kie": "queue:kie-submit",
}

# arq's default `poll_delay` (0.5s) means every one of `worker/settings.py`'s
# four `WorkerSettings` classes plus `worker/cron.py`'s `CronWorker` — five
# independent polling loops, by design (ADR 0014: one per provider so one's
# slowness can't delay another's) — hits Redis roughly twice a second each,
# whether or not there's a real job waiting. That cost scales with how long
# the worker process is *running*, not with how many jobs it actually does:
# a real Upstash account here burned through half its 500K/month free
# command budget from local dev alone, with only a handful of real jobs
# submitted the whole time. 5s cuts each loop's poll rate — and therefore
# its Redis command volume — to roughly a tenth of the 0.5s default, at the
# cost of up to ~5s of extra pickup latency per job. Accepted: every create
# page is fire-and-forget with an SSE push on completion (ADR 0018), so
# nobody is watching a spinner for those extra seconds either way.
WORKER_POLL_DELAY_SECONDS = 5.0


def redis_settings() -> RedisSettings:
    """Built fresh from the current settings each call (cheap — just parses
    a URL) rather than cached, so `WorkerSettings` classes (evaluated at
    import time, one per worker process) and the web process's own pool
    (built at startup, see `main.py`) always agree on where Redis is."""
    return RedisSettings.from_dsn(get_settings().redis_url)


_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    """The web process's own connection, used only to enqueue — opened once
    at startup (`main.py`'s lifespan), reused for the process's lifetime."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def enqueue(function: str, *, job_id: str, queue_name: str, **task_kwargs: Any) -> bool:
    """Enqueues one task, calling it as `function(ctx, job_id=job_id, **task_kwargs)`
    — every task in `worker/tasks.py` takes `job_id` as its first real
    argument, so this always forwards it, not just uses it internally.

    `job_id` is *separately* passed as arq's own `_job_id` too — arq
    de-duplicates on that (a second `enqueue()` with the same id is a
    no-op, returning `None` instead of a new `Job`), which makes retrying
    the enqueue call itself (e.g. after a transient connection error) safe
    to do without risking a job running twice. Returns `False` only when
    arq recognizes the id as already enqueued; a real connection failure
    raises instead of returning `False`, so callers can tell "already
    queued" apart from "Redis is unreachable" (`services/jobs.py` treats
    the latter as ADR 0014's "enqueue failure" path: release the hold, fail
    the job)."""
    pool = await get_pool()
    job = await pool.enqueue_job(
        function, job_id=job_id, _job_id=job_id, _queue_name=queue_name, **task_kwargs
    )
    return job is not None
