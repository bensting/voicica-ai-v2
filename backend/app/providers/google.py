"""Google Cloud Text-to-Speech adapter.

Verified against texttospeech.googleapis.com with a plain API key (no
service account needed for this API, unlike Firebase Admin):
- `GET /v1/voices?key=...` returns every voice: `languageCodes[]`/`name`/`ssmlGender`.
- `POST /v1/text:synthesize?key=...` is synchronous — JSON in, JSON out with
  `audioContent` as base64 (not raw bytes like Azure/Fish Audio) — decoded
  here so services/jobs.py never has to know the difference between
  providers. Confirmed working for both an English and a Thai
  (`th-TH-Chirp3-HD-Achernar`) voice.
"""

from base64 import b64decode
from typing import Any

import httpx

from app.providers.base import JobRef, Provider

_BASE_URL = "https://texttospeech.googleapis.com/v1"


class GoogleProvider(Provider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        if capability != "tts":
            raise ValueError(f"GoogleProvider doesn't support capability={capability!r}")
        return await self._synthesize(inputs)

    async def _synthesize(self, inputs: dict[str, Any]) -> JobRef:
        text = inputs["text"]
        voice = inputs.get("provider_voice_id")
        locale = inputs.get("locale")
        if not voice or not locale:
            # Google's `voice` object requires both languageCode and name — no
            # default voice to fall back to. Same defensive-only check as Azure.
            return JobRef(
                status="failed",
                error="Google TTS requires a selected voice (no default voice exists).",
            )

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": locale, "name": voice},
            "audioConfig": {"audioEncoding": "MP3"},
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{_BASE_URL}/text:synthesize",
                    params={"key": self._api_key},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobRef(status="failed", error=f"Google TTS {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Google TTS request failed: {exc}")

        audio_b64 = response.json()["audioContent"]
        return JobRef(
            status="succeeded",
            output={"audio_bytes": b64decode(audio_b64), "content_type": "audio/mpeg"},
        )

    async def list_voices(self) -> list[dict[str, Any]]:
        """Raw Google voice dicts, for app/scheduled/sync_catalog.py. Not on
        any user request path (ADR 0007)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{_BASE_URL}/voices", params={"key": self._api_key})
            response.raise_for_status()
            return response.json()["voices"]
