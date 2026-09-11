"""Azure Speech (Cognitive Services) adapter — TTS.

Verified against a real Azure Speech resource (region: southeastasia):
- `GET https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list`
  (header `Ocp-Apim-Subscription-Key`) returns the full voice catalog —
  `ShortName`/`DisplayName`/`Gender`/`Locale`/`StyleList` per voice.
- `POST .../cognitiveservices/v1` is synchronous — SSML in, raw audio bytes
  out (same shape as Fish Audio) — no polling needed. Confirmed working for
  both an English and a Thai (`th-TH-PremwadeeNeural`) voice.
"""

from typing import Any
from xml.sax.saxutils import escape

import httpx

from app.providers.base import JobRef, Provider


class AzureProvider(Provider):
    def __init__(self, api_key: str, region: str) -> None:
        self._api_key = api_key
        self._region = region
        self._base_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices"

    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        if capability != "tts":
            raise ValueError(f"AzureProvider doesn't support capability={capability!r}")
        return await self._synthesize(inputs)

    async def _synthesize(self, inputs: dict[str, Any]) -> JobRef:
        text = inputs["text"]
        voice = inputs.get("provider_voice_id")
        locale = inputs.get("locale")
        if not voice or not locale:
            # Unlike Fish Audio, Azure has no "default voice" to fall back to —
            # <voice name="..."> is required by its SSML. services/jobs.py only
            # ever routes here once a voice_catalog row supplied both, so this
            # is a defensive check, not an expected path.
            return JobRef(
                status="failed",
                error="Azure Speech requires a selected voice (no default voice exists).",
            )

        ssml = (
            f'<speak version="1.0" xml:lang="{locale}">'
            f'<voice name="{voice}">{escape(text)}</voice></speak>'
        )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self._base_url}/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": self._api_key,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
                    },
                    content=ssml.encode("utf-8"),
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobRef(status="failed", error=f"Azure Speech {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Azure Speech request failed: {exc}")

        return JobRef(
            status="succeeded",
            output={"audio_bytes": response.content, "content_type": "audio/mpeg"},
        )

    async def list_voices(self) -> list[dict[str, Any]]:
        """Raw Azure voice dicts, for app/scheduled/sync_catalog.py to map into
        voice_catalog rows. Not called on any user request path (ADR 0007 —
        catalog sync is off the request path on purpose)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/voices/list",
                headers={"Ocp-Apim-Subscription-Key": self._api_key},
            )
            response.raise_for_status()
            return response.json()
