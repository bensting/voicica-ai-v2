"""Selects a concrete provider for a capability (ADR 0001).

Business logic (`services/`) never imports `fish_audio.py`/`azure.py`/etc.
directly — only this module. Today there's one provider per capability and no
fallback; the fallback/cost-routing logic this ADR anticipates (try vendor B
if vendor A fails) belongs entirely here later, without `services/` changing.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import Provider
from app.providers.fish_audio import FishAudioProvider

# capability -> ordered list of provider names to try (first only, for now)
_CAPABILITY_PROVIDERS: dict[str, list[str]] = {
    "tts": ["fish_audio"],
}


@lru_cache
def _build_providers() -> dict[str, Provider]:
    settings = get_settings()
    providers: dict[str, Provider] = {}
    if settings.fish_audio_api_key:
        providers["fish_audio"] = FishAudioProvider(
            api_key=settings.fish_audio_api_key, base_url=settings.fish_audio_base_url
        )
    return providers


def get_provider(capability: str) -> Provider:
    """Returns the provider to use for a capability. Raises if none is configured
    (e.g. FISH_AUDIO_API_KEY missing) — a clear startup-time-shaped error, not a
    silent None that surfaces confusingly deep in a request.
    """
    provider_names = _CAPABILITY_PROVIDERS.get(capability)
    if not provider_names:
        raise ValueError(f"No provider configured for capability={capability!r}")

    providers = _build_providers()
    for name in provider_names:
        if name in providers:
            return providers[name]

    raise RuntimeError(
        f"capability={capability!r} needs one of {provider_names!r}, "
        "but none has credentials configured (check .env)"
    )
