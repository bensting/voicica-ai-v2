"""kie_models gains provider_model_id + fixed_inputs (ADR 0017) — separates
"our own catalog id" from "the literal string sent to Kie", needed because
Veo 3.1's Lite/Fast/Quality tiers are all really `provider_model_id="veo-3-1"`.
Existing rows backfill provider_model_id = model_id (unchanged behavior).

Also seeds the new image-to-video category + 2 models (Grok Imagine Video
1.5, Veo 3.1 Lite — the latter starts disabled, see kie_catalog.py).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.kie_catalog import _SEED_CATEGORIES, _SEED_MODELS

revision: str = "0011"
down_revision: str | None = "0010"
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
    sa.column("provider_model_id", sa.String),
    sa.column("fixed_inputs", postgresql.JSONB),
    sa.column("category_id", sa.String),
    sa.column("display_name", sa.String),
    sa.column("input_schema", postgresql.JSONB),
    sa.column("pricing", postgresql.JSONB),
    sa.column("enabled", sa.Boolean),
)

_NEW_CATEGORY_IDS = {"image-to-video"}
_new_categories = [c for c in _SEED_CATEGORIES if c["id"] in _NEW_CATEGORY_IDS]
_new_models = [m for m in _SEED_MODELS if m["category_id"] in _NEW_CATEGORY_IDS]


def upgrade() -> None:
    op.add_column("kie_models", sa.Column("provider_model_id", sa.String(128), nullable=True))
    op.execute("UPDATE kie_models SET provider_model_id = model_id WHERE provider_model_id IS NULL")
    op.alter_column("kie_models", "provider_model_id", nullable=False)

    op.add_column(
        "kie_models",
        sa.Column("fixed_inputs", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.alter_column("kie_models", "fixed_inputs", server_default=None)

    op.bulk_insert(kie_categories, _new_categories)
    op.bulk_insert(kie_models, _new_models)


def downgrade() -> None:
    model_ids = [m["model_id"] for m in _new_models]
    op.execute(kie_models.delete().where(kie_models.c.model_id.in_(model_ids)))
    op.execute(kie_categories.delete().where(kie_categories.c.id.in_(_NEW_CATEGORY_IDS)))

    op.drop_column("kie_models", "fixed_inputs")
    op.drop_column("kie_models", "provider_model_id")
