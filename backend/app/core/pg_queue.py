"""The job queue itself (ADR 0026) — a `jobs` row *is* the queue entry;
there's no separate Redis/arq queue anymore. Two halves live here:

- `notify_job_ready()` — called by `services/jobs.py` right after committing
  a new `pending` row, on the caller's own (pooled) session. Sending a
  notification works fine over a pooled connection; only *receiving* one
  (`LISTEN`) needs the direct connection below.
- `listen_for_jobs()` — the dispatcher's (`worker/dispatcher.py`) one
  long-lived, non-pooled connection. Verified live against Neon: a pooled
  connection never receives a notification sent by another session (the
  pooler can hand each transaction a different backend connection), so
  this must use `DATABASE_DIRECT_URL`, not `DATABASE_URL`.

Claiming (`claim_pending_jobs`) is `SELECT ... FOR UPDATE SKIP LOCKED`,
same idiom used everywhere else in this codebase for "two things racing on
the same row must not double-process it" (`finalize_kie_job`,
`billing.complete_purchase`) — applied here to the queue's own claim step
instead of a downstream settlement step.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CHANNEL = "jobs_ready"


async def notify_job_ready(db: AsyncSession) -> None:
    """Fire-and-forget wake-up signal — best-effort, same posture as
    `services/jobs.py publish_job_event()`. A missed notification (the
    dispatcher briefly disconnected, a race between commit and LISTEN
    registration) is never the only way a job gets picked up — the
    dispatcher's own fallback poll (worker/dispatcher.py) covers that, the
    same "push primary, poll fallback" shape as Kie's webhook (ADR 0015)."""
    try:
        await db.execute(text("SELECT pg_notify(:channel, '')"), {"channel": _CHANNEL})
    except Exception:
        logger.warning("notify_job_ready: failed to send, relying on fallback poll", exc_info=True)


def _direct_dsn() -> str:
    settings = get_settings()
    dsn = settings.database_direct_url or settings.database_url
    # SQLAlchemy's driver prefix (`postgresql+asyncpg://`) isn't valid for
    # raw asyncpg.connect() — this connection bypasses SQLAlchemy entirely.
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def listen_for_jobs() -> AsyncIterator[asyncio.Event]:
    """Opens the one direct connection the whole dispatcher process needs,
    LISTENs on it, and yields an `asyncio.Event` that gets set every time a
    notification arrives (cleared by the caller after waking up). A context
    manager so the connection is always closed on shutdown, not leaked."""
    settings = get_settings()
    conn = await asyncpg.connect(_direct_dsn(), ssl="require" if settings.database_ssl_require else None)
    event = asyncio.Event()

    def _on_notify(*_args: object) -> None:
        event.set()

    await conn.add_listener(_CHANNEL, _on_notify)
    try:
        yield event
    finally:
        await conn.remove_listener(_CHANNEL, _on_notify)
        await conn.close()
