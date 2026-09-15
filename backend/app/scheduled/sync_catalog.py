"""Provider catalog sync (ADR 0007) — pulls Azure/Google's own voice lists
into `voice_catalog`. Fish Audio isn't synced yet: unlike these two, its
"official voices" list endpoint hasn't been verified against real
credentials, so it's left out rather than guessed at — its TTS flow still
works via a raw provider_voice_id (voice cloning, ADR 0009), just outside
the picker until that's researched.

Callable directly for now (ADR 0007 leaves the actual scheduling mechanism
open, pending a hosting decision) — run manually:
    python -m app.scheduled.sync_catalog
(see backend/README.md).
"""

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.providers.azure import AzureProvider
from app.providers.google import GoogleProvider
from app.services import voice_catalog


def _azure_rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "provider_voice_id": v["ShortName"],
            "locale": v["Locale"],
            "display_name": v["DisplayName"],
            "gender": (v.get("Gender") or "").lower() or None,
            "styles": v.get("StyleList"),
        }
        for v in raw
    ]


def _google_rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "provider_voice_id": v["name"],
            # Google doesn't give a separate human-readable name — the voice
            # name itself (e.g. "en-US-Standard-C") is the only label it has,
            # so display_name just duplicates provider_voice_id (frontend's
            # friendlyVoiceName() does the actual cosmetic cleanup at render
            # time, never stored). Missing here entirely until a real
            # resync against a fresh database — the first one this ran
            # against — hit `display_name`'s NOT NULL constraint on every
            # single Google row: real proof this line was needed all along,
            # not a defensive addition against a hypothetical.
            "display_name": v["name"],
            # locale is stored exactly as Google returns it (e.g. "cmn-CN",
            # its own code for Mandarin) — this is also what gets sent back
            # to Google as `languageCode` at generation time (providers/
            # google.py), and Google's API rejects anything that doesn't
            # match a voice's own code exactly (verified: "zh-CN" against a
            # cmn-CN voice 400s). The cmn/zh grouping-for-browsing alias
            # lives in services/voice_catalog.py instead, query-side only —
            # never rewrite this field.
            "locale": v["languageCodes"][0],
            "gender": (v.get("ssmlGender") or "").lower() or None,
            "styles": None,
        }
        for v in raw
        if v.get("languageCodes")
    ]


async def sync_all(db: AsyncSession) -> dict[str, int]:
    """Returns {provider: voice count synced} for whichever providers have
    credentials configured — silently skips the rest, same posture as
    providers/registry.py's _build_providers()."""
    settings = get_settings()
    counts: dict[str, int] = {}

    if settings.azure_speech_key and settings.azure_speech_region:
        azure = AzureProvider(api_key=settings.azure_speech_key, region=settings.azure_speech_region)
        raw = await azure.list_voices()
        counts["azure"] = await voice_catalog.replace_provider_catalog(
            db, provider="azure", rows=_azure_rows(raw)
        )

    if settings.google_tts_api_key:
        google = GoogleProvider(api_key=settings.google_tts_api_key)
        raw = await google.list_voices()
        counts["google"] = await voice_catalog.replace_provider_catalog(
            db, provider="google", rows=_google_rows(raw)
        )

    return counts


async def _main() -> None:
    from app.core.db import async_session_factory  # local import: only this script needs it

    async with async_session_factory() as db:
        counts = await sync_all(db)
        for provider, count in counts.items():
            print(f"{provider}: synced {count} voices")


if __name__ == "__main__":
    asyncio.run(_main())
