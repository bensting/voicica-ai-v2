"""Seed the capability menu (the "+" button's sheet) into app_settings.
Only `tts` is enabled — the rest are placeholders ready to flip on once
their capability exists, per the discussion in CLAUDE.md.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.menu import _DEFAULT_ITEMS, _KEY

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
)


def upgrade() -> None:
    op.bulk_insert(app_settings, [{"key": _KEY, "value": {"value": _DEFAULT_ITEMS}}])


def downgrade() -> None:
    op.execute(app_settings.delete().where(app_settings.c.key == _KEY))
