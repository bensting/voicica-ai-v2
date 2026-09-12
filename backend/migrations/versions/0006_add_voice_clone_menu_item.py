"""Add the "voice-clone" item to the capability menu (ADR 0009's feature
going live) and enable it — 0003 seeded the menu before this capability
existed. A wholesale overwrite of the `capability_menu` app_settings row
with the current `_DEFAULT_ITEMS`, same approach 0003 used to seed it in
the first place (simpler and safer than patching one entry inside the
stored JSON array in raw SQL).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.menu import _DEFAULT_ITEMS, _KEY

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
)

# The pre-0006 shape (order renumbered to make room for "voice-clone" at 2),
# so downgrade can restore it exactly rather than just deleting the row.
_PREVIOUS_ITEMS = [
    {**item, "order": item["order"] - 1}
    for item in _DEFAULT_ITEMS
    if item["id"] != "voice-clone"
]


def upgrade() -> None:
    op.execute(
        app_settings.update()
        .where(app_settings.c.key == _KEY)
        .values(value={"value": _DEFAULT_ITEMS})
    )


def downgrade() -> None:
    op.execute(
        app_settings.update()
        .where(app_settings.c.key == _KEY)
        .values(value={"value": _PREVIOUS_ITEMS})
    )
