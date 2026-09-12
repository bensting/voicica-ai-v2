"""Add `voice_models.title` — a real incident exposed its absence: with no
name stored, `GET /voice-models` had nothing to show but an identical
placeholder for every voice, which is exactly how someone else's real
cloned voice got mistaken for leftover test data and deleted. The name the
user already types into `POST /voice-models`'s `title` form field (used as
Fish Audio's own model title) was never persisted on our own row — it is
now.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # server_default only so this is safe against any pre-existing row (none
    # in practice — every write from here on always supplies a real title,
    # POST /voice-models' `title` form field is required).
    op.add_column(
        "voice_models", sa.Column("title", sa.String(50), nullable=False, server_default="")
    )
    op.alter_column("voice_models", "title", server_default=None)


def downgrade() -> None:
    op.drop_column("voice_models", "title")
