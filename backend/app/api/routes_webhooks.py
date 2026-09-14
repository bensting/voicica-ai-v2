"""POST /webhooks/kie — Kie's `callBackUrl` target (ADR 0015,
architecture.md §3d): the primary Kie-completion path, with
`worker/cron.py`'s poll sweep as the fallback for anything missed.

No signature/secret to verify — not documented by Kie, so this endpoint
trusts only `taskId` to find *a* job, then re-derives everything else via
`provider.poll()` rather than the webhook body itself (`services/jobs.py`
`finalize_kie_job`'s own docstring explains why: one source of truth for
what a terminal Kie job looks like). That keeps the blast radius of a
forged/replayed call low — at worst it triggers a redundant, harmless
`recordInfo` poll for a `taskId` an attacker would already have to know;
it can't fabricate a result or move credits on its own."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.models import Job
from app.providers.registry import get_provider_by_name
from app.services import jobs

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/kie", status_code=200)
async def kie_webhook(payload: dict[str, Any], db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    task_id = (payload.get("data") or {}).get("taskId") or payload.get("taskId")
    if not task_id:
        return {"ok": False}

    job = (
        await db.execute(select(Job).where(Job.provider_job_id == task_id))
    ).scalar_one_or_none()
    if job is None:
        # Not necessarily an error — a retried/duplicate callback for a job
        # this backend never actually submitted (or already knows by a
        # different id) shouldn't 500 and cause Kie to keep retrying.
        return {"ok": False}

    provider = get_provider_by_name("kie")
    job_status = await provider.poll(task_id)
    await jobs.finalize_kie_job(db, job.id, job_status)
    return {"ok": True}
