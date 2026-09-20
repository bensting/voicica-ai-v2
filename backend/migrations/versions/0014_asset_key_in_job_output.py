"""Rewrite jobs.output's `asset_url` (a `/jobs/{id}/asset` proxy path) to the
plain R2 object key `asset_key` (ADR 0027: clients now load media straight
from R2's public domain, the proxy route is gone, and the URL is derived at
response time from the key). Data-only — no schema change. Rows whose asset
isn't `done` (nothing in R2) just lose the dead `asset_url` field.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET output = (output - 'asset_url') || jsonb_build_object('asset_key', a.r2_key)
        FROM assets a
        WHERE a.job_id = jobs.id
          AND a.mirror_status = 'done'
          AND jobs.output ? 'asset_url'
        """
    )
    op.execute(
        """
        UPDATE jobs
        SET output = output - 'asset_url'
        WHERE output ? 'asset_url'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET output = (output - 'asset_key') || jsonb_build_object('asset_url', '/jobs/' || jobs.id::text || '/asset')
        WHERE output ? 'asset_key' AND output->>'asset_key' IS NOT NULL
        """
    )
