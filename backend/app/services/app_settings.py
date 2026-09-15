"""Reads/writes `app_settings` — simple tunable scalars, not engineering config
(ADR 0012). Distinct from `core/config.py`, which holds secrets/env-specific
values that genuinely do need a deploy to change.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AppSetting

# Fallback used only if a key has never been written to the DB (fresh install,
# before seeding). Once a row exists, the DB value always wins — these are not
# "the real values", just what unblocks a brand new environment.
_DEFAULTS: dict[str, Any] = {
    "signup_bonus_credits": 50,
    "tts_credits_per_10_chars": 1,
    # Fish Audio's TTS model (providers/fish_audio.py) — a scalar an admin
    # should be able to bump the moment Fish ships a new recommended model,
    # without a deploy. Read fresh per-request (no caching), same as
    # tts_credits_per_10_chars above; PATCH /admin/settings/fish_tts_model
    # (already generic, no new endpoint needed) is how it's changed.
    "fish_tts_model": "s2.1-pro",
}


async def get_setting(db: AsyncSession, key: str) -> Any:
    row = await db.get(AppSetting, key)
    if row is not None:
        return row.value["value"]
    if key in _DEFAULTS:
        return _DEFAULTS[key]
    raise KeyError(f"Unknown app_settings key: {key!r}")


async def set_setting(db: AsyncSession, key: str, value: Any, updated_by: str | None) -> AppSetting:
    row = await db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value={"value": value}, updated_by=updated_by)
        db.add(row)
    else:
        row.value = {"value": value}
        row.updated_by = updated_by
    return row


async def list_settings(db: AsyncSession) -> dict[str, Any]:
    """All known settings — DB rows where they exist, defaults for the rest,
    so an admin always sees the complete, current picture."""
    from sqlalchemy import select

    rows = (await db.execute(select(AppSetting))).scalars().all()
    result = dict(_DEFAULTS)
    for row in rows:
        result[row.key] = row.value["value"]
    return result
