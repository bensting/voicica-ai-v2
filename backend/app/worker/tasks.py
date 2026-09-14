"""arq task functions — thin plumbing around `services/jobs.py`'s
`execute_*` functions (ADR 0014). This is the one module that imports both
`arq` and the business logic together; `services/jobs.py` itself stays
queue-agnostic (it raises the plain `TransientProviderError`, not arq's
own `Retry` — only this module knows arq exists).

Each task opens its own DB session (`async_session_factory()` directly, not
`Depends(get_db)` — there's no request here) — never a request's session,
which is the whole point of moving these off the request path.
"""

import uuid
from typing import Any

from arq import Retry

from app.core.db import async_session_factory
from app.services import jobs

# Backoff between retries of a transient provider failure: try 2 is delayed
# 5s, try 3 is delayed 10s, etc. — `services/jobs.MAX_PROVIDER_TRIES` bounds
# how many tries a job gets in total (matched by `max_tries` on the
# `func()`-wrapped tasks in `worker/settings.py`).
_RETRY_BACKOFF_SECONDS = 5


async def run_tts_job(ctx: dict[str, Any], job_id: str) -> None:
    async with async_session_factory() as db:
        try:
            await jobs.execute_tts_job(db, uuid.UUID(job_id), job_try=ctx["job_try"])
        except jobs.TransientProviderError as exc:
            raise Retry(defer=_RETRY_BACKOFF_SECONDS * ctx["job_try"]) from exc


async def run_voice_model_training_job(
    ctx: dict[str, Any], job_id: str, *, audio_bytes: bytes, audio_filename: str
) -> None:
    async with async_session_factory() as db:
        try:
            await jobs.execute_voice_model_training_job(
                db,
                uuid.UUID(job_id),
                audio_bytes=audio_bytes,
                audio_filename=audio_filename,
                job_try=ctx["job_try"],
            )
        except jobs.TransientProviderError as exc:
            raise Retry(defer=_RETRY_BACKOFF_SECONDS * ctx["job_try"]) from exc


async def run_kie_submit_job(ctx: dict[str, Any], job_id: str) -> None:
    """ADR 0014/0015's `queue:kie-submit` task — calls Kie's createTask only
    and returns; never waits for Kie to finish generating. Completion
    arrives later via `POST /webhooks/kie` or `worker/cron.py`'s poll sweep,
    both calling `jobs.finalize_kie_job`, never this task again."""
    async with async_session_factory() as db:
        try:
            await jobs.execute_kie_submit_job(db, uuid.UUID(job_id), job_try=ctx["job_try"])
        except jobs.TransientProviderError as exc:
            raise Retry(defer=_RETRY_BACKOFF_SECONDS * ctx["job_try"]) from exc
