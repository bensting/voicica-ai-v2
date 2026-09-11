"""Google Cloud Text-to-Speech adapter.

Verified against texttospeech.googleapis.com with a plain API key (no
service account needed for this API, unlike Firebase Admin):
- `GET /v1/voices?key=...` returns every voice: `languageCodes[]`/`name`/`ssmlGender`.
- `POST /v1/text:synthesize?key=...` is synchronous — JSON in, JSON out with
  `audioContent` as base64 (not raw bytes like Azure/Fish Audio) — decoded
  here so services/jobs.py never has to know the difference between
  providers. Confirmed working for both an English and a Thai
  (`th-TH-Chirp3-HD-Achernar`) voice.
- `audioConfig.pitch` is rejected outright by some newer voices (verified:
  Chirp3 HD, 400 "This voice does not support pitch parameters") —
  `_synthesize` retries once without it on that specific error.
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

        # speed/volume/pitch: one provider-agnostic scale (schemas.TTSRequest,
        # docstring on services/jobs.py's submit_tts), converted to Google's
        # own audioConfig units — formulas ported from the prior project's
        # verified conversion: speakingRate is speed as-is (already inside
        # Google's wider 0.25-4.0 range); pitch (pitch-50)*0.4 maps 1-100 onto
        # roughly Google's -20..20 semitone range; volumeGainDb (volume-50)*0.2
        # maps 1-100 onto a modest -9.8..10 dB (well inside Google's -96..16).
        speed = inputs.get("speed", 1.0)
        volume = inputs.get("volume", 50)
        pitch = inputs.get("pitch", 50)
        speaking_rate = max(0.25, min(4.0, speed))
        pitch_value = (pitch - 50) * 0.4
        volume_gain_db = (volume - 50) * 0.2

        audio_config = {
            "audioEncoding": "MP3",
            "speakingRate": speaking_rate,
            "pitch": pitch_value,
            "volumeGainDb": volume_gain_db,
        }
        payload = {
            "input": {"text": text},
            "voice": {"languageCode": locale, "name": voice},
            "audioConfig": audio_config,
        }

        try:
            response = await self._post_synthesize(payload)
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            # Some voices (e.g. Chirp3 HD) reject `pitch` outright — verified
            # against the real API (400, "This voice does not support pitch
            # parameters..."); retry once without it rather than failing the
            # whole request over a parameter this voice just doesn't take.
            if exc.response.status_code == 400 and "pitch" in body and pitch_value != 0:
                retry_payload = {
                    **payload,
                    "audioConfig": {k: v for k, v in audio_config.items() if k != "pitch"},
                }
                try:
                    response = await self._post_synthesize(retry_payload)
                except httpx.HTTPStatusError as retry_exc:
                    return JobRef(
                        status="failed",
                        error=f"Google TTS {retry_exc.response.status_code}: {retry_exc.response.text[:300]}",
                    )
                except httpx.HTTPError as retry_exc:
                    return JobRef(status="failed", error=f"Google TTS request failed: {retry_exc}")
            else:
                return JobRef(status="failed", error=f"Google TTS {exc.response.status_code}: {body[:300]}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Google TTS request failed: {exc}")

        audio_b64 = response.json()["audioContent"]
        return JobRef(
            status="succeeded",
            output={"audio_bytes": b64decode(audio_b64), "content_type": "audio/mpeg"},
        )

    async def _post_synthesize(self, payload: dict[str, Any]) -> httpx.Response:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{_BASE_URL}/text:synthesize", params={"key": self._api_key}, json=payload
            )
            response.raise_for_status()
            return response

    async def list_voices(self) -> list[dict[str, Any]]:
        """Raw Google voice dicts, for app/scheduled/sync_catalog.py. Not on
        any user request path (ADR 0007)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{_BASE_URL}/voices", params={"key": self._api_key})
            response.raise_for_status()
            return response.json()["voices"]
