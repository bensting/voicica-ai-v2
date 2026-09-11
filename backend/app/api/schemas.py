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
    reference_id: str | None = Field(
        default=None, description="A voice_catalog entry or an owned voice model's provider id"
    )


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
