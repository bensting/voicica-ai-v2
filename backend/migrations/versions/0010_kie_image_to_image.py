"""image-to-image — a second Kie category (ADR 0016), 4 models (Flux-2
Pro/Flex, GPT Image 2.5 Flare/Sunburst — each's image-to-image sibling to
the text-to-image model 0009 already seeded). Confirms `kie_categories`/
`kie_models` (ADR 0015) really do scale by adding rows, not code: this
migration is data only, same shape as 0009, no schema change.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.kie_catalog import _SEED_CATEGORIES, _SEED_MODELS

revision: str = "0010"
down_revision: str | None = "0009"
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

_NEW_CATEGORY_IDS = {"image-to-image"}
_new_categories = [c for c in _SEED_CATEGORIES if c["id"] in _NEW_CATEGORY_IDS]
_new_models = [m for m in _SEED_MODELS if m["category_id"] in _NEW_CATEGORY_IDS]


def upgrade() -> None:
    op.bulk_insert(kie_categories, _new_categories)
    op.bulk_insert(kie_models, _new_models)


def downgrade() -> None:
    model_ids = [m["model_id"] for m in _new_models]
    op.execute(kie_models.delete().where(kie_models.c.model_id.in_(model_ids)))
    op.execute(kie_categories.delete().where(kie_categories.c.id.in_(_NEW_CATEGORY_IDS)))
