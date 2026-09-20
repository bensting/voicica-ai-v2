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
    # tts | voice_model_training | <a kie_categories.id, e.g. "text-to-image"> (ADR 0015) —
    # for a Kie job this is the model's own category, not a fixed enum member,
    # since the catalog (and so the set of real values here) grows by data.
    capability: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))  # azure | google | fish_audio | kie
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Kie only

    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processing|succeeded|failed
    provider_state: Mapped[str | None] = mapped_column(String(32), nullable=True)  # raw vendor state
    # Kie's own taskId (ADR 0015) — set once `execute_kie_submit_job` calls
    # createTask, so the webhook (looked up by this) and the poll-sweep cron
    # (worker/cron.py) can both find their way back to this row. Every other
    # provider is synchronous (submit() already returns terminal), so this
    # is always null for them.
    provider_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

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

    # ADR 0026 — replace arq's own in-memory retry counter and delayed-
    # requeue scheduling now that the queue itself is a plain `jobs` row,
    # not an arq/Redis entry. `tries` starts at 0 (nothing attempted yet);
    # the dispatcher claims a row and calls execute_*_job with
    # `job_try=job.tries + 1`, matching arq's old 1-indexed `ctx["job_try"]`.
    # `run_after` is NULL for "claimable right away" — set to a future
    # timestamp only when a transient-error retry is scheduled with a
    # backoff delay (worker/dispatcher.py), the direct replacement for
    # arq's own delayed-retry sorted-set scheduling.
    tries: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)

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


class KieCategory(Base):
    """One row per Kie capability category, e.g. "text-to-image" (ADR 0015)
    — hand-curated, never synced (Kie exposes no catalog/pricing API,
    verified). `output_type` selects which frontend result-renderer a
    category's jobs use (image/video/audio); adding a category whose
    output_type already has a renderer is a pure data change end to end."""

    __tablename__ = "kie_categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "text-to-image"
    display_name: Mapped[str] = mapped_column(String(128))
    output_type: Mapped[str] = mapped_column(String(16))  # image | video | audio
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class KieModel(Base):
    """One row per *catalog* model (ADR 0015) — `model_id` is our own
    catalog's identifier (routing, display, `Job.model_id`), not always the
    same as what's literally sent to Kie. `provider_model_id` is that real
    Kie string (e.g. "flux-2/pro-text-to-image") — usually equal to
    `model_id`, except when one real Kie model bundles several logically
    distinct offerings behind an input field rather than separate model
    strings (Veo 3.1's Lite/Fast/Quality tiers all really are
    `provider_model_id="veo-3-1"` — verified against a real API call, ADR
    0017): each tier still gets its own catalog row (own price, own display
    name, own place in the model list) for the same reason Flux-2 Pro/Flex
    already do, with `fixed_inputs` pinning the one field the tier actually
    changes (`{"model": "veo3_fast"}`) — invisible to `input_schema`/the
    user, merged into `input` at submission (services/jobs.py submit_kie_job).

    `input_schema` drives the frontend's generic form; `pricing` drives the
    credit hold at submission — settlement always uses Kie's own
    `creditsConsumed` instead (services/jobs.py finalize_kie_job), never
    this table."""

    __tablename__ = "kie_models"

    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("kie_categories.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    # The literal string sent as createTask's top-level "model" (ADR 0017).
    # Equal to model_id for every model catalogued before Veo 3.1 — kept
    # ourselves, never assumed the same as our own catalog id going forward.
    provider_model_id: Mapped[str] = mapped_column(String(128))
    # [{name, label, type: select|text|number|image|boolean, options?, default, required}, ...]
    input_schema: Mapped[list] = mapped_column(JSONB)
    # {"param": "resolution", "costs": {"1K": 5, "2K": 7}} (lookup) or
    # {"flat": N} or {"rate_param": "duration", "tier_param": "resolution",
    # "rates": {"480p": 2.4, ...}} (per-unit formula, ADR 0017) — see ADR 0015/0017.
    pricing: Mapped[dict] = mapped_column(JSONB)
    # Extra `input` fields this catalog row pins for every submission —
    # never shown in input_schema, never user-editable (ADR 0017). {} for
    # every model where the catalog row and the real Kie model are 1:1.
    fixed_inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


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
    # The name the user gave it at training time (POST /voice-models' `title`
    # form field) — added after a real incident: with no name stored, every
    # voice rendered as an identical, indistinguishable placeholder in the
    # picker, which is exactly how someone else's real cloned voice got
    # mistaken for leftover test data and deleted (migration 0008).
    title: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(32))  # fish_audio only for now (ADR 0009's open item)
    provider_model_id: Mapped[str] = mapped_column(String(128))  # Fish Audio's own model _id
    state: Mapped[str] = mapped_column(String(16), default="training")  # training | ready | failed
    created_from_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())


class CreditPurchase(Base):
    """One row per attempted Stripe Checkout Session for a credit pack
    (ADR 0024) — created `pending` at session-creation time, before the user
    has paid anything, so a webhook that arrives has a real row to find and
    lock. `credits`/`amount_usd_cents` are a snapshot of the package's price
    *at purchase time* — `app_settings.credit_packages` (ADR 0012) can
    change later without rewriting history.

    `stripe_checkout_session_id` is the idempotency key: Stripe's webhook
    delivery is at-least-once (the same lesson ADR 0014 already learned the
    hard way with arq), so `services/billing.py complete_purchase()` locks
    this row (`SELECT ... FOR UPDATE`, same idiom as `finalize_kie_job`)
    and only tops up credits if `status` is still `pending` — a redelivered
    webhook for an already-completed purchase safely no-ops instead of
    double-crediting the wallet."""

    __tablename__ = "credit_purchases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    package_key: Mapped[str] = mapped_column(String(32))  # app_settings.credit_packages[].key
    credits: Mapped[int] = mapped_column(Integer)
    amount_usd_cents: Mapped[int] = mapped_column(Integer)
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|completed|failed
    created_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(_TZ, nullable=True)


class AppSetting(Base):
    """Generic key-value store for tunable scalars (ADR 0012) — e.g.
    signup_bonus_credits, tts_credits_per_10_chars. Read by any service that
    needs the value; written only through PATCH /admin/settings/{key}."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(_TZ, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
