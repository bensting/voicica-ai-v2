"""The public gallery (ADR 0010) — reads `jobs` where `visibility = public`
and a mirrored asset is actually ready. No separate content system; this is
the whole implementation.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Asset, Job

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


async def list_public(
    db: AsyncSession, *, cursor: str | None = None, limit: int = _DEFAULT_LIMIT
) -> tuple[list[Job], str | None]:
    """Newest-first, cursor-paginated. Cursor is the previous page's last
    item's `created_at` (ISO 8601) — simple rather than opaque, since
    nothing here is sensitive; two jobs sharing a microsecond-precision
    timestamp is the one known edge case (a row could be skipped), accepted
    for now rather than adding a compound (created_at, id) cursor."""
    limit = max(1, min(limit, _MAX_LIMIT))

    query = (
        select(Job)
        .join(Asset, Asset.job_id == Job.id)
        .where(Job.visibility == "public", Asset.mirror_status == "done")
        .order_by(Job.created_at.desc())
        .limit(limit + 1)  # one extra row tells us whether there's a next page
    )
    if cursor:
        query = query.where(Job.created_at < datetime.fromisoformat(cursor))

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = page[-1].created_at.isoformat() if has_more and page else None
    return page, next_cursor
