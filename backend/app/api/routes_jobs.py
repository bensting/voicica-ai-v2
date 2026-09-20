"""GET /jobs, GET /jobs/{id}, PATCH /jobs/{id} — docs/api-contract.md "Jobs".
Media bytes are never served from here: a job's `output.asset_url` points
straight at R2's public domain (ADR 0027)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import JobResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.models.models import Job
from app.services import app_settings
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    # History only spans the retention window (ADR 0027) — past it, the files
    # are gone, so the rows would just be dead entries.
    retention_days = await app_settings.get_setting(db, "asset_retention_days")
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    rows = (
        await db.execute(
            select(Job)
            .where(Job.user_id == user.id, Job.created_at >= cutoff)
            .order_by(Job.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [JobResponse.model_validate(row) for row in rows]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await jobs_service.get_job(db, job_id, user_id=user.id)
    if job is None:
        raise APIError(status_code=404, code="not_found", message="No such job.")
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job_visibility(
    job_id: uuid.UUID,
    visibility: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """ADR 0010 — the only field this can change. `visibility` as a query
    param keeps this endpoint to exactly the one thing it's for."""
    if visibility not in ("private", "public"):
        raise APIError(status_code=422, code="invalid_input", message="visibility must be 'private' or 'public'.")

    job = await jobs_service.get_job(db, job_id, user_id=user.id)
    if job is None:
        raise APIError(status_code=404, code="not_found", message="No such job.")
    if job.status != "succeeded":
        raise APIError(
            status_code=422, code="invalid_input", message="Only a succeeded job can be made public."
        )

    job.visibility = visibility
    await db.commit()  # see the comment in services/jobs.py submit_tts — same reasoning
    return JobResponse.model_validate(job)
