"""Redis, kept for exactly one purpose now (ADR 0026): the pub/sub channel
`services/jobs.py publish_job_event()` publishes to and `api/routes_events.py`
subscribes from (ADR 0018's SSE push). The job queue itself moved to
Postgres (`core/pg_queue.py`, `worker/dispatcher.py`) — polling 5 arq
worker loops was burning through Upstash's free-tier command budget
(measured: ~250K/month from local dev alone, nowhere near real production
traffic) for work that didn't need Redis's queue semantics, only its
pub/sub ones. Pub/sub itself was never the cost driver — it's push-based
by nature, proportional to real activity (a PUBLISH per job completion, a
SUBSCRIBE per open SSE connection), not a fixed per-second polling cost —
so it stays.
"""

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings


def redis_settings() -> RedisSettings:
    """Built fresh from the current settings each call (cheap — just parses
    a URL) rather than cached, so the web process's own pool (built at
    startup, see `main.py`) always uses the current config."""
    return RedisSettings.from_dsn(get_settings().redis_url)


_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    """The one Redis connection this process needs — opened once at startup
    (`main.py`'s lifespan), reused for the process's lifetime. Still typed
    as `ArqRedis` (arq's own thin wrapper over redis-py) purely because it's
    a convenient async Redis client already in this dependency tree, not
    because arq's queue features are used here anymore."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
