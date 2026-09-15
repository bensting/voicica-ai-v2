"""Seed app_settings placeholder values (ADR 0012). Tunable anytime via
PATCH /admin/settings/{key} — these are starting points, not final numbers.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SEED = {
    "signup_bonus_credits": 50,
    "tts_credits_per_10_chars": 1,
}

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
)


def upgrade() -> None:
    op.bulk_insert(
        app_settings,
        [{"key": key, "value": {"value": value}} for key, value in _SEED.items()],
    )


def downgrade() -> None:
    op.execute(
        app_settings.delete().where(app_settings.c.key.in_(list(_SEED.keys())))
    )
