"""POST /generate/kie + GET /kie/categories, /kie/models (ADR 0015) — the
generic, catalog-driven Kie surface. One route handles every Kie model,
regardless of category: `model_id` in the request body picks both the
category and the schema/pricing rule (`kie_models`), the same way TTS's
`voice_id` already picks a provider without a route per provider.
"""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.api.schemas import (
    JobResponse,
    KieCategoryResponse,
    KieGenerateRequest,
    KieModelResponse,
    KieUploadResponse,
)
from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_db
from app.services import assets as assets_service
from app.services import credits, jobs
from app.services import kie_catalog as kie_catalog_service

router = APIRouter(tags=["kie"])

# A reference image, not a video — generous upper bound against an
# oversized upload (same reasoning/shape as routes_voice_models.py's audio
# cap), not a tuned limit.
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


@router.get("/kie/categories", response_model=list[KieCategoryResponse])
async def list_categories(
    _user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[KieCategoryResponse]:
    return await kie_catalog_service.list_categories(db)


@router.get("/kie/models", response_model=list[KieModelResponse])
async def list_models(
    category_id: str | None = None,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KieModelResponse]:
    models = await kie_catalog_service.list_models(db, category_id=category_id)
    # output_type is denormalized from the category (ADR 0017) so the
    # frontend never needs a second fetch to know which result renderer a
    # model needs — one categories lookup for the whole list, not per row.
    categories = {c.id: c.output_type for c in await kie_catalog_service.list_categories(db)}
    return [_to_model_response(m, categories.get(m.category_id, "")) for m in models]


@router.get("/kie/models/{model_id:path}", response_model=KieModelResponse)
async def get_model(
    model_id: str,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KieModelResponse:
    # `:path` converter — real model_id values contain a literal "/" (e.g.
    # "flux-2/pro-text-to-image", verified against Kie's own API), which a
    # plain FastAPI path param would otherwise split into two segments.
    model = await kie_catalog_service.get_model(db, model_id)
    if model is None or not model.enabled:
        raise APIError(status_code=404, code="not_found", message="No such Kie model.")
    category = await kie_catalog_service.get_category(db, model.category_id)
    return _to_model_response(model, category.output_type if category else "")


def _to_model_response(model, output_type: str) -> KieModelResponse:
    """`KieModelResponse.model_validate(model, from_attributes=True)` can't
    fill in `output_type` on its own — it's denormalized from the model's
    category, not a `KieModel` column (ADR 0017) — so this constructs the
    response explicitly instead of relying on attribute-matching."""
    return KieModelResponse(
        model_id=model.model_id,
        category_id=model.category_id,
        display_name=model.display_name,
        output_type=output_type,
        input_schema=model.input_schema,
        pricing=model.pricing,
    )


@router.post("/kie/uploads", response_model=KieUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_reference_image(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> KieUploadResponse:
    """ADR 0016: a Kie image-to-image model's `input_urls` field needs a
    real, unauthenticated URL Kie's own servers can fetch — this uploads to
    a short-lived public R2 location and hands back that URL. The caller
    (`POST /generate/kie`) is responsible for including the returned
    `r2_key` in its own request's tracking so the upload gets cleaned up
    once the job it's for reaches a terminal state; this endpoint itself
    doesn't know which job (if any) will end up using it."""
    extension = _ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise APIError(
            status_code=422,
            code="invalid_input",
            message="Only PNG, JPEG, or WebP images are supported.",
        )
    data = await file.read()
    if not data:
        raise APIError(status_code=422, code="invalid_input", message="File is empty.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise APIError(status_code=422, code="invalid_input", message="File is too large.")

    try:
        result = await assets_service.upload_public_bytes(
            owner_id=user.id, data=data, content_type=file.content_type, extension=extension
        )
    except RuntimeError as exc:
        raise APIError(status_code=503, code="upload_unavailable", message=str(exc)) from exc
    return KieUploadResponse(**result)


@router.post(
    "/generate/kie",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_kie_job(
    body: KieGenerateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    try:
        job = await jobs.submit_kie_job(
            db,
            user_id=user.id,
            model_id=body.model_id,
            inputs=body.inputs,
            uploaded_r2_keys=body.uploaded_r2_keys,
            visibility=body.visibility,
        )
    except credits.InsufficientCreditsError as exc:
        raise APIError(
            status_code=402,
            code="insufficient_credits",
            message=f"This would cost {exc.required} credits; you have {exc.available}.",
        ) from exc
    except ValueError as exc:
        raise APIError(status_code=400, code="invalid_model", message=str(exc)) from exc
    except jobs.EnqueueError as exc:
        raise APIError(
            status_code=503,
            code="queue_unavailable",
            message="Couldn't queue this job right now — please try again.",
        ) from exc

    return JobResponse.model_validate(job)
