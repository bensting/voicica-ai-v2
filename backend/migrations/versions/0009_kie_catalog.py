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
