"""POST/GET/DELETE /voice-models — voice cloning (ADR 0009,
docs/api-contract.md "Voice models"). Training is a job submission (like
`POST /generate/tts`), so it returns the same `JobResponse` shape — just
multipart instead of JSON, since it carries an audio file rather than text.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import JobResponse, VoiceModelResponse
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import jobs, voice_models

router = APIRouter(prefix="/voice-models", tags=["voice-models"])

# A cloned-voice sample is a short clip (the frontend's recorder caps at 30s,
# matching the prior project's own AudioUploader) — this is a generous upper
# bound against an oversized upload, not a tuned limit.
_MAX_SAMPLE_BYTES = 15 * 1024 * 1024


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_voice_model(
    title: str = Form(..., min_length=1, max_length=50),
    reference_text: str | None = Form(default=None, max_length=500),
    audio: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise APIError(status_code=422, code="invalid_input", message="Audio sample is empty.")
    if len(audio_bytes) > _MAX_SAMPLE_BYTES:
        raise APIError(status_code=422, code="invalid_input", message="Audio sample is too large.")

    try:
        job = await jobs.submit_voice_model_training(
            db,
            user_id=user.id,
            title=title,
            audio_bytes=audio_bytes,
            audio_filename=audio.filename or "sample.mp3",
            reference_text=reference_text,
        )
    except jobs.EnqueueError as exc:
        # ADR 0014: Redis unreachable at enqueue time — see routes_tts.py's
        # identical handling for why this is 503, not a 4xx.
        raise APIError(
            status_code=503,
            code="queue_unavailable",
            message="Couldn't queue this job right now — please try again.",
        ) from exc
    return JobResponse.model_validate(job)


@router.get("", response_model=list[VoiceModelResponse])
async def list_voice_models(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[VoiceModelResponse]:
    rows = await voice_models.list_ready(db, user_id=user.id)
    return [VoiceModelResponse.model_validate(row) for row in rows]


@router.delete("/{voice_model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_model(
    voice_model_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await voice_models.delete(db, voice_model_id, user_id=user.id)
    if not deleted:
        raise APIError(status_code=404, code="not_found", message="No such voice.")
