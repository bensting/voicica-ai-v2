"""Pydantic request/response shapes — the runtime counterpart of docs/api-contract.md."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
        "provider it belongs to. Omit for the default voice (Fish Audio).",
    )


class VoiceCatalogResponse(BaseModel):
    """GET /catalog/voices — one synced voice."""

    id: uuid.UUID
    provider: str
    locale: str
    display_name: str
    gender: str | None
    styles: list[str] | None

    model_config = {"from_attributes": True}


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
