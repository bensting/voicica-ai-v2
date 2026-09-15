"""kie_categories/kie_models — the hand-curated Kie model catalog (ADR 0015),
plus jobs.provider_job_id (needed so the Kie webhook/poll-sweep can find
their way back to a job from Kie's own taskId — every other provider is
synchronous and never sets this).

Seeds the real first catalog entries (text-to-image: Flux-2 Pro/Flex,
GPT Image 2.5 Flare/Sunburst) from app/services/kie_catalog.py's own
constants — same pattern 0003 used for the capability menu.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.kie_catalog import _SEED_CATEGORIES, _SEED_MODELS

# `app/services/kie_catalog.py`'s _SEED_CATEGORIES/_SEED_MODELS are live
# constants that later ADRs (0016, 0017) kept appending to — 0010/0011
# already filter down to just the category they're each responsible for
# seeding; this migration predates that pattern and needs the same fix,
# or running the full chain against a fresh database (never exercised
# until now — every real database this ran against had these migrations
# applied one at a time, as each was written, when the constants were
# still small) bulk-inserts rows 0010/0011 then try to insert again,
# failing on a duplicate primary key. Real bug, caught this way.
_OWN_CATEGORY_IDS = {"text-to-image"}
_SEED_CATEGORIES = [c for c in _SEED_CATEGORIES if c["id"] in _OWN_CATEGORY_IDS]
_SEED_MODELS = [m for m in _SEED_MODELS if m["category_id"] in _OWN_CATEGORY_IDS]

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

kie_categories = sa.table(
    "kie_categories",
    sa.column("id", sa.String),
    sa.column("display_name", sa.String),
    sa.column("output_type", sa.String),
    sa.column("enabled", sa.Boolean),
)
kie_models = sa.table(
    "kie_models",
    sa.column("model_id", sa.String),
    sa.column("category_id", sa.String),
    sa.column("display_name", sa.String),
    sa.column("input_schema", postgresql.JSONB),
    sa.column("pricing", postgresql.JSONB),
    sa.column("enabled", sa.Boolean),
)


def upgrade() -> None:
    op.add_column("jobs", sa.Column("provider_job_id", sa.String(128), nullable=True))
    op.create_index("ix_jobs_provider_job_id", "jobs", ["provider_job_id"])

    op.create_table(
        "kie_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("output_type", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "kie_models",
        sa.Column("model_id", sa.String(128), primary_key=True),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("kie_categories.id"), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("input_schema", postgresql.JSONB, nullable=False),
        sa.Column("pricing", postgresql.JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kie_models_category_id", "kie_models", ["category_id"])

    op.bulk_insert(kie_categories, _SEED_CATEGORIES)
    op.bulk_insert(kie_models, _SEED_MODELS)


def downgrade() -> None:
    op.drop_index("ix_kie_models_category_id", table_name="kie_models")
    op.drop_table("kie_models")
    op.drop_table("kie_categories")
    op.drop_index("ix_jobs_provider_job_id", table_name="jobs")
    op.drop_column("jobs", "provider_job_id")
