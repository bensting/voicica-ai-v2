"""Fix `jobs.voice_model_id`'s FK to `ON DELETE SET NULL` — 0005 created it
with Postgres's default `RESTRICT`, which a real test caught immediately:
deleting a voice model failed with a ForeignKeyViolationError because both
the training job that created it and any TTS job that used it still
reference its id. A job's history entry should survive its voice being
deleted (the historical fact "this job used this voice" doesn't stop being
true) — the `voice_model_id` column pointing at nothing is exactly what
`nullable=True` already anticipated; RESTRICT just made that unreachable.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_jobs_voice_model_id", "jobs", type_="foreignkey")
    op.create_foreign_key(
        "fk_jobs_voice_model_id",
        "jobs",
        "voice_models",
        ["voice_model_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_voice_model_id", "jobs", type_="foreignkey")
    op.create_foreign_key(
        "fk_jobs_voice_model_id", "jobs", "voice_models", ["voice_model_id"], ["id"]
    )
