"""ORM models — the authoritative schema is docs/data-model.md; this implements it.

Conventions (docs/data-model.md "Conventions"): UUID primary keys, snake_case,
timestamptz in UTC, money/credits as integers, no soft-delete by default.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func

# Every timestamp column is timestamptz (docs/data-model.md "Conventions": UTC
# always) — SQLAlchemy's `datetime` type annotation alone maps to a *naive*
# DateTime, which silently mismatches a tz-aware Python value at the driver
# level (asyncpg then refuses to bind it). Every datetime column below is
# explicit about `DateTime(timezone=True)` because of that, not by habit.
_TZ = DateTime(timezone=True)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    """One row per authenticated identity. id = Firebase UID (ADR 0008)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # Firebase UID, not a UUID we generate
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | staff | admin
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())

    wallet: Mapped["CreditWallet"] = relationship(back_populates="user", uselist=False)


class CreditWallet(Base):
    """One per user (1:1). `balance` is cached, kept in sync with credit_transactions
    inside the same DB transaction as every write (ADR 0003)."""

    __tablename__ = "credit_wallets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="wallet")


class CreditTransaction(Base):
    """Append-only audit ledger — every topup/hold/settle/release event (ADR 0003)."""

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_wallets.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # topup | hold | settle | release
    amount: Mapped[int] = mapped_column(Integer)  # signed
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class Job(Base):
    """One row per generation request, covering every capability uniformly (ADR 0002)."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    capability: Mapped[str] = mapped_column(String(32))  # tts | voice_model_training | image | music | video
    provider: Mapped[str] = mapped_column(String(32))  # azure | google | fish_audio | kie
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Kie only

    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processing|succeeded|failed
    provider_state: Mapped[str | None] = mapped_column(String(32), nullable=True)  # raw vendor state

    input: Mapped[dict] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    estimated_cost: Mapped[int] = mapped_column(Integer)
    actual_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hold_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_holds.id"), nullable=True)

    # Set when this TTS job used an owned, cloned voice (ADR 0009) instead of
    # a voice_catalog row — mutually exclusive with input["voice_id"]; also
    # set (to the row it created) on a voice_model_training job itself.
    # ON DELETE SET NULL (migration 0007, fixed after a real test caught
    # Postgres's default RESTRICT blocking `DELETE /voice-models/{id}` on a
    # voice any job — training or TTS — had ever referenced): a job's
    # history should survive its voice being deleted, not pin it forever.
    voice_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("voice_models.id", ondelete="SET NULL"), nullable=True
    )
    visibility: Mapped[str] = mapped_column(String(8), default="private")  # private | public (ADR 0010)

    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)

    asset: Mapped["Asset | None"] = relationship(back_populates="job", uselist=False)


class CreditHold(Base):
    """One per job (1:1) — its own lifecycle/timestamps, queried directly for
    the available-balance calculation (ADR 0003)."""

    __tablename__ = "credit_holds"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | settled | released
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)


class Asset(Base):
    """One per successfully mirrored job (ADR 0004). Absence (or mirror_status
    != done) means nothing is in R2 yet for that job."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), unique=True)
    r2_key: Mapped[str] = mapped_column(String(512))
    mirror_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|failed
    mirrored_at: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="asset")


class VoiceCatalog(Base):
    """A synced mirror of Azure/Google/Fish Audio's own voice lists
    (docs/data-model.md, ADR 0007) — read-only from the backend's perspective,
    overwritten wholesale on each sync run (app/scheduled/sync_catalog.py).
    No FK from `jobs` — a job stores `provider`/`input.provider_voice_id`
    directly (docs/data-model.md §"voice_catalog"), so this table can be
    resynced/pruned independently of job history."""

    __tablename__ = "voice_catalog"
    __table_args__ = (Index("ix_voice_catalog_provider_locale", "provider", "locale"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(32))  # azure | google | fish_audio
    provider_voice_id: Mapped[str] = mapped_column(String(128))  # e.g. "th-TH-PremwadeeNeural"
    locale: Mapped[str] = mapped_column(String(16))  # e.g. "th-TH"
    display_name: Mapped[str] = mapped_column(String(128))
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    styles: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # supported emotions/styles, if any
    synced_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class VoiceModel(Base):
    """One row per voice a user has cloned (ADR 0009) — a durable asset the
    user owns, not subject to R2 retention (ADR 0004) the way generated
    media is; persists until deleted. Created by a `voice_model_training`
    job (`created_from_job_id`, audit-only — nothing depends on it at read
    time); consumed by an ordinary `tts` job that sets `Job.voice_model_id`
    instead of picking a `voice_catalog` row."""

    __tablename__ = "voice_models"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))  # fish_audio only for now (ADR 0009's open item)
    provider_model_id: Mapped[str] = mapped_column(String(128))  # Fish Audio's own model _id
    state: Mapped[str] = mapped_column(String(16), default="training")  # training | ready | failed
    created_from_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class AppSetting(Base):
    """Generic key-value store for tunable scalars (ADR 0012) — e.g.
    signup_bonus_credits, tts_credits_per_10_chars. Read by any service that
    needs the value; written only through PATCH /admin/settings/{key}."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
