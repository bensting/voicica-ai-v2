"""Initial schema — implements docs/data-model.md for this slice
(users, credit_wallets, credit_transactions, jobs, credit_holds, assets,
app_settings). voice_catalog and voice_models are out of scope for this
slice (ADR 0007, ADR 0009) and aren't created yet.

Revision ID: 0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "credit_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("capability", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("provider_state", sa.String(32), nullable=True),
        sa.Column("input", postgresql.JSONB, nullable=False),
        sa.Column("output", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("estimated_cost", sa.Integer, nullable=False),
        sa.Column("actual_cost", sa.Integer, nullable=True),
        sa.Column("hold_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voice_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visibility", sa.String(8), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "status"])

    op.create_table(
        "credit_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False, unique=True),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_credit_holds_user_id", "credit_holds", ["user_id"])

    op.create_foreign_key(
        "fk_jobs_hold_id", "jobs", "credit_holds", ["hold_id"], ["id"]
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("credit_wallets.id"), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_credit_transactions_wallet_id", "credit_transactions", ["wallet_id"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False, unique=True),
        sa.Column("r2_key", sa.String(512), nullable=False),
        sa.Column("mirror_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("mirrored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(128), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("assets")
    op.drop_index("ix_credit_transactions_wallet_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_constraint("fk_jobs_hold_id", "jobs", type_="foreignkey")
    op.drop_index("ix_credit_holds_user_id", table_name="credit_holds")
    op.drop_table("credit_holds")
    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("credit_wallets")
    op.drop_table("users")
