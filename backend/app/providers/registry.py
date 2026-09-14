"""Selects a concrete provider for a capability, or by name (ADR 0001).

Business logic (`services/`) never imports `fish_audio.py`/`azure.py`/etc.
directly — only this module. Two lookup shapes exist:
- `get_provider(capability)` — capability-level default/fallback (today:
  one entry per capability, no fallback yet; the fallback/cost-routing logic
  ADR 0001 anticipates belongs here later without `services/` changing).
- `get_provider_by_name(name)` — used when the caller already knows which
  provider a request must go to (TTS: the voice the user picked came from a
  specific provider's voice_catalog row — see services/jobs.py submit_tts).
"""

from functools import lru_cache

from app.core.config import get_settings
from app.providers.azure import AzureProvider
from app.providers.base import Provider
from app.providers.fish_audio import FishAudioProvider
from app.providers.google import GoogleProvider
from app.providers.kie import KieProvider

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
    if settings.azure_speech_key and settings.azure_speech_region:
        providers["azure"] = AzureProvider(
            api_key=settings.azure_speech_key, region=settings.azure_speech_region
        )
    if settings.google_tts_api_key:
        providers["google"] = GoogleProvider(api_key=settings.google_tts_api_key)
    if settings.kie_api_key:
        providers["kie"] = KieProvider(
            api_key=settings.kie_api_key,
            base_url=settings.kie_base_url,
            callback_base_url=settings.public_base_url,
        )
    return providers


def get_provider(capability: str) -> Provider:
    """Returns the default provider for a capability, for a capability that
    genuinely has one fixed vendor (not TTS — every TTS request already
    knows which provider it needs, from the voice or voice model picked;
    see get_provider_by_name below). Not called by anything in this slice
    yet — kept for the capabilities ADR 0001 anticipates needing real
    fallback/cost-routing logic here (Kie's image/video, once built).
    Raises if none is configured (e.g. FISH_AUDIO_API_KEY missing) — a clear
    startup-time-shaped error, not a silent None surfacing confusingly deep
    in a request.
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


def get_provider_by_name(name: str) -> Provider:
    """Returns a specific provider, e.g. the one a chosen voice_catalog row
    belongs to. Raises the same shape of error as get_provider() if that
    provider's credentials aren't configured."""
    providers = _build_providers()
    if name not in providers:
        raise RuntimeError(f"provider={name!r} has no credentials configured (check .env)")
    return providers[name]
