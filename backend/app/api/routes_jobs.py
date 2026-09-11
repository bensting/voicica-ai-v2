"""GET /jobs, GET /jobs/{id}, PATCH /jobs/{id}, GET /jobs/{id}/asset —
docs/api-contract.md "Jobs" (the last one isn't in that doc yet — added
because the browser needs *something* to fetch audio from; see
services/assets.py for why it's a proxy, not a presigned R2 URL)."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import JobResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.models.models import Job
from app.services import assets as assets_service
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    rows = (
        await db.execute(
            select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(50)
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


@router.get("/{job_id}/asset")
async def get_job_asset(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    job = await jobs_service.get_job_with_asset(db, job_id, user_id=user.id)
    if job is None or job.asset is None or job.asset.mirror_status != "done":
        raise APIError(status_code=404, code="not_found", message="No asset for this job.")
    data, content_type = await assets_service.download_bytes(job.asset.r2_key)
    return Response(content=data, media_type=content_type)
