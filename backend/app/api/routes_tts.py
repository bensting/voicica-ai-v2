"""POST /generate/tts — docs/api-contract.md "Submitting a capability"."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import JobResponse, TTSRequest
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import credits, jobs

router = APIRouter(tags=["generate"])


@router.post(
    "/generate/tts",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_tts_job(
    body: TTSRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    try:
        job = await jobs.submit_tts(
            db,
            user_id=user.id,
            text=body.text,
            voice_id=body.voice_id,
            speed=body.speed,
            volume=body.volume,
            pitch=body.pitch,
            visibility=body.visibility,
        )
    except credits.InsufficientCreditsError as exc:
        raise APIError(
            status_code=402,
            code="insufficient_credits",
            message=f"This would cost {exc.required} credits; you have {exc.available}.",
        ) from exc
    except ValueError as exc:
        raise APIError(status_code=400, code="invalid_voice", message=str(exc)) from exc

    return JobResponse.model_validate(job)
