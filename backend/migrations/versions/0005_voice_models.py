"""voice_models — a user's own cloned voices (docs/data-model.md, ADR 0009),
not present in the initial schema (0001's own docstring notes it as
deferred). `jobs.voice_model_id` already existed as a bare column (reserved
by 0001) — this adds the real FK now that the table it points to exists,
same pattern 0001 used for `jobs.hold_id` -> credit_holds.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_model_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="training"),
        sa.Column("created_from_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_voice_models_user_id", "voice_models", ["user_id"])

    op.create_foreign_key(
        "fk_jobs_voice_model_id", "jobs", "voice_models", ["voice_model_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_voice_model_id", "jobs", type_="foreignkey")
    op.drop_index("ix_voice_models_user_id", table_name="voice_models")
    op.drop_table("voice_models")
