"""Add jobs.tries/run_after — replaces arq's own retry counter and delayed-
requeue scheduling (ADR 0026: Postgres-native job queue, no more Redis for
dispatch). A partial index on the claim query's exact WHERE shape keeps
`SELECT ... FOR UPDATE SKIP LOCKED` cheap regardless of table growth.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("tries", sa.Integer, nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("run_after", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_jobs_pending_claim",
        "jobs",
        ["run_after"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_pending_claim", table_name="jobs")
    op.drop_column("jobs", "run_after")
    op.drop_column("jobs", "tries")
