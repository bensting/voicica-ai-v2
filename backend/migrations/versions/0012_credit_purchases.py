"""Add credit_purchases table + seed app_settings.credit_packages (ADR 0024).

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Real pricing decision (not a placeholder like most other seeded values in
# this table) — three one-time packs, volume-discounted per credit ($0.0090
# -> $0.0079 -> $0.0067). Tunable anytime via PATCH /admin/settings/
# credit_packages, same as every other app_settings value.
_CREDIT_PACKAGES = [
    {"key": "small", "label": "Starter", "credits": 1000, "price_usd_cents": 900},
    {"key": "medium", "label": "Pro", "credits": 12500, "price_usd_cents": 9900},
    {"key": "large", "label": "Studio", "credits": 29500, "price_usd_cents": 19900},
]

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
)


def upgrade() -> None:
    op.create_table(
        "credit_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("package_key", sa.String(32), nullable=False),
        sa.Column("credits", sa.Integer, nullable=False),
        sa.Column("amount_usd_cents", sa.Integer, nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_credit_purchases_user_id", "credit_purchases", ["user_id"])
    op.create_index(
        "ix_credit_purchases_stripe_checkout_session_id",
        "credit_purchases",
        ["stripe_checkout_session_id"],
        unique=True,
    )

    op.bulk_insert(
        app_settings,
        [{"key": "credit_packages", "value": {"value": _CREDIT_PACKAGES}}],
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'credit_packages'")
    op.drop_index("ix_credit_purchases_stripe_checkout_session_id", table_name="credit_purchases")
    op.drop_index("ix_credit_purchases_user_id", table_name="credit_purchases")
    op.drop_table("credit_purchases")
