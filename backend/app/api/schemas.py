"""Pydantic request/response shapes — the runtime counterpart of docs/api-contract.md."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services import assets as assets_service


class ErrorBody(BaseModel):
    """docs/api-contract.md "Conventions" — every error is {"error": {code, message}}."""

    code: str
    message: str


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    balance: int


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: uuid.UUID | None = Field(
        default=None,
        description="A voice_catalog row's id (GET /catalog/voices) — picking a voice picks the "
        "provider it belongs to. Exactly one of voice_id/voice_model_id is required (no "
        "default voice — Fish Audio isn't a general fallback, it's reserved for a user's own "
        "cloned voices, see voice_model_id below).",
    )
    voice_model_id: uuid.UUID | None = Field(
        default=None,
        description="A voice_models row's id (GET /voice-models) — a user's own cloned voice "
        "(ADR 0009) instead of a catalog voice. Exactly one of voice_id/voice_model_id "
        "is required.",
    )
    # Same 3-parameter, provider-agnostic scale for every provider (docs/api-contract.md):
    # speed 0.5-2.0x, volume/pitch 1-100 centered on 50. Each adapter converts to its own
    # units (services/jobs.py's docstring on submit_tts has the exact formulas, ported from
    # the prior project's verified-in-production conversions).
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: int = Field(default=50, ge=1, le=100)
    pitch: int = Field(default=50, ge=1, le=100)
    # ADR 0010: opt-in, set explicitly — defaults to private like the column
    # itself. Lets a user share at creation time instead of only after the
    # fact via PATCH /jobs/{id} (which still exists, for changing your mind
    # later — this doesn't replace it, just adds the earlier option).
    visibility: str = Field(default="private", pattern="^(private|public)$")

    @model_validator(mode="after")
    def _exactly_one_voice(self) -> "TTSRequest":
        if (self.voice_id is None) == (self.voice_model_id is None):
            raise ValueError("Provide exactly one of voice_id or voice_model_id.")
        return self


class VoiceCatalogResponse(BaseModel):
    """GET /catalog/voices — one synced voice."""

    id: uuid.UUID
    provider: str
    locale: str
    display_name: str
    gender: str | None
    styles: list[str] | None

    model_config = {"from_attributes": True}


class LanguageOption(BaseModel):
    """GET /catalog/languages — one selectable base language ("es", not
    "es-MX") for the voice picker's dropdown, with how many voices it has
    across every provider/locale variant combined. Grouped by base language
    rather than exact locale because providers don't carve a language into
    countries the same way (Azure has ~22 Spanish locales, Google has 2) —
    see services/voice_catalog.py's module docstring."""

    language: str
    voice_count: int


class VoiceModelResponse(BaseModel):
    """GET /voice-models — one of the current user's own cloned voices
    (ADR 0009). Only `ready` ones are ever returned (services/voice_models.py).
    `title` is the name given at training time — added after a real incident
    where its absence made every voice render as an identical, indistinguishable
    placeholder, and someone else's real cloned voice got mistaken for
    leftover test data and deleted."""

    id: uuid.UUID
    title: str
    provider: str
    state: str
    created_at: datetime

    model_config = {"from_attributes": True}


class KieGenerateRequest(BaseModel):
    """POST /generate/kie — category-agnostic (ADR 0015): `model_id` picks
    both the category and the provider, the same way TTS's `voice_id` picks
    a provider (services/jobs.py submit_kie_job). `inputs` is passed through
    to Kie's own `input` object verbatim — its shape is whatever that
    model's `kie_models.input_schema` (GET /kie/models) declares, validated
    against the catalog's pricing rule at submission, not by this schema."""

    model_id: str
    inputs: dict[str, Any]
    visibility: str = Field(default="private", pattern="^(private|public)$")
    # ADR 0016: r2_key(s) from POST /kie/uploads that this job's `inputs`
    # references (e.g. inside an `input_urls` field) — tracked so they can
    # be deleted the moment this job reaches a terminal state, not kept for
    # the generated-output retention window. Empty for a text-to-image job.
    uploaded_r2_keys: list[str] = Field(default_factory=list)

    # "model_id" collides with Pydantic v2's own reserved "model_" prefix
    # (model_dump, model_validate, ...) — harmless here (this is a plain
    # data field, not one of those), just silencing the warning.
    model_config = {"protected_namespaces": ()}


class KieCategoryResponse(BaseModel):
    """GET /kie/categories — lets the frontend build one generic capability
    page per category, driven by `output_type` (which result-renderer to
    use) rather than a hardcoded per-category component."""

    id: str
    display_name: str
    output_type: str

    model_config = {"from_attributes": True}


class KieModelResponse(BaseModel):
    """GET /kie/models?category_id= — the schema-driven form (ADR 0015)
    reads `input_schema` to render its fields; `pricing` is exposed too so
    the frontend can show a live cost estimate as the user picks values,
    the same way Kie's own playground shows a "N credits · Run" button.
    `output_type` is denormalized from this model's category (ADR 0017) so
    the generation page knows which result renderer to use without a
    second fetch. `provider_model_id`/`fixed_inputs` (ADR 0017) are
    deliberately not exposed here — purely a backend implementation detail
    of how this catalog row maps onto Kie's real API, never the client's
    business."""

    model_id: str
    category_id: str
    display_name: str
    output_type: str
    input_schema: list[dict[str, Any]]
    pricing: dict[str, Any]

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class KieModelAdmin(BaseModel):
    """POST/PATCH /admin/kie-models — every field, for editing.
    `provider_model_id` defaults to `model_id` (every model catalogued
    before ADR 0017 has them equal) — only pass a different value when one
    real Kie model is being split into several catalog rows (Veo 3.1's
    quality tiers); `fixed_inputs` pins whatever field distinguishes such a
    row, invisible to `input_schema`."""

    model_id: str
    provider_model_id: str | None = None
    fixed_inputs: dict[str, Any] = Field(default_factory=dict)
    category_id: str
    display_name: str
    input_schema: list[dict[str, Any]]
    pricing: dict[str, Any]
    enabled: bool = True

    model_config = {"protected_namespaces": (), "from_attributes": True}


class KieModelPatch(BaseModel):
    """PATCH /admin/kie-models/{model_id} — every field optional."""

    provider_model_id: str | None = None
    fixed_inputs: dict[str, Any] | None = None
    category_id: str | None = None
    display_name: str | None = None
    input_schema: list[dict[str, Any]] | None = None
    pricing: dict[str, Any] | None = None
    enabled: bool | None = None

    model_config = {"protected_namespaces": ()}


class KieUploadResponse(BaseModel):
    """POST /kie/uploads (ADR 0016) — a short-lived public URL for a Kie
    image-to-image reference image. `r2_key` is only needed by the caller if
    it later wants to reference this exact upload; the frontend itself only
    ever needs `url` (placed into an `input_urls`-shaped field's value)."""

    url: str
    r2_key: str


class KieCategoryAdmin(BaseModel):
    """POST/PATCH /admin/kie-categories."""

    id: str
    display_name: str
    output_type: str
    enabled: bool = True

    model_config = {"from_attributes": True}


def _resolve_asset_url(output: dict[str, Any] | None) -> dict[str, Any] | None:
    """A job's stored `output` holds only the R2 object key (`asset_key`);
    clients get a ready-to-load `asset_url` instead (ADR 0027) — built here,
    at response time, so the serving domain can change without touching any
    stored row. `asset_key` itself never leaves the backend."""
    if not output or "asset_key" not in output:
        return output
    resolved = {k: v for k, v in output.items() if k != "asset_key"}
    resolved["asset_url"] = assets_service.public_url(output["asset_key"])
    return resolved


class JobResponse(BaseModel):
    id: uuid.UUID
    capability: str
    provider: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    estimated_cost: int
    actual_cost: int | None
    visibility: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}

    _output_asset_url = field_validator("output", mode="after")(_resolve_asset_url)


class AdminJobResponse(JobResponse):
    """GET /admin/jobs (ADR 0020) — the one field `JobResponse` deliberately
    leaves out for its normal, single-user callers (`GET /jobs`): whose job
    this is. An admin job monitor spanning every user is useless without it."""

    user_id: str


class GalleryItemResponse(BaseModel):
    """GET /gallery — one public creation (ADR 0010). Deliberately leaner
    than JobResponse: no estimated_cost/actual_cost/error/visibility — those
    are the owner's own business, not something a gallery viewer (possibly
    not even the owner) needs. No creator identity either — ADR 0010 doesn't
    call for attribution, keep it that way until actually asked for."""

    id: uuid.UUID
    capability: str
    provider: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}

    _output_asset_url = field_validator("output", mode="after")(_resolve_asset_url)


class GalleryPage(BaseModel):
    """docs/api-contract.md "Conventions" — the standard cursor-pagination
    envelope. `next_cursor` is the last item's created_at (ISO 8601);
    pass it back as `?cursor=` for the next page, null when there isn't one."""

    items: list[GalleryItemResponse]
    next_cursor: str | None


class CreditGrantRequest(BaseModel):
    amount: int
    reason: str


class SettingUpdateRequest(BaseModel):
    value: Any


class MenuItemResponse(BaseModel):
    """GET /config/menu — one locale's worth of text already resolved, so the
    frontend does zero lookup of its own (docs: "no frontend config" for
    dynamic content)."""

    id: str
    icon: str
    route: str
    badge: str | None
    label: str
    description: str


class MenuItemAdmin(BaseModel):
    """GET/POST/PATCH /admin/menu — every locale, for editing."""

    id: str
    icon: str
    route: str
    enabled: bool
    order: int
    badge: str | None = None
    labels: dict[str, str]
    descriptions: dict[str, str]


class MenuItemPatch(BaseModel):
    """PATCH /admin/menu/{id} — every field optional, only what's set changes."""

    icon: str | None = None
    route: str | None = None
    enabled: bool | None = None
    order: int | None = None
    badge: str | None = None
    labels: dict[str, str] | None = None
    descriptions: dict[str, str] | None = None
