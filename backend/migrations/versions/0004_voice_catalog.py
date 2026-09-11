"""voice_catalog — a synced mirror of Azure/Google/Fish Audio's voice lists
(docs/data-model.md, ADR 0007), not present in the initial schema (0001's
own docstring notes it as deferred). No FK to `jobs` — see the table's
model docstring in app/models/models.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_voice_id", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column("styles", postgresql.JSONB, nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_voice_catalog_provider_locale", "voice_catalog", ["provider", "locale"]
    )


def downgrade() -> None:
    op.drop_index("ix_voice_catalog_provider_locale", table_name="voice_catalog")
    op.drop_table("voice_catalog")
