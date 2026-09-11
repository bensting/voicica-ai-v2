"""Fish Audio adapter — TTS today; voice cloning (ADR 0009) is a later addition.

Verified against https://docs.fish.audio/api-reference/introduction
(see architecture.md §3e):
- `POST /v1/tts` is synchronous — it streams audio directly in the response.
  `submit()` therefore always returns an already-terminal `JobRef`.
- Voice cloning (`POST /model`) is a separate, two-stage flow (ADR 0009) —
  not implemented here yet; this slice only covers `capability == "tts"`.
"""

from typing import Any

import httpx

from app.providers.base import JobRef, Provider


class FishAudioProvider(Provider):
    def __init__(self, api_key: str, base_url: str = "https://api.fish.audio") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        if capability != "tts":
            raise ValueError(
                f"FishAudioProvider doesn't support capability={capability!r} in this slice "
                "(voice cloning training is ADR 0009, not yet implemented)"
            )
        return await self._synthesize(inputs)

    async def _synthesize(self, inputs: dict[str, Any]) -> JobRef:
        text = inputs["text"]
        # "provider_voice_id" is the uniform key every TTS adapter reads
        # (services/jobs.py, resolved from a voice_catalog row or an owned
        # voice model) — Fish Audio's own API just happens to call its
        # version of this parameter "reference_id".
        reference_id = inputs.get("provider_voice_id")

        payload: dict[str, Any] = {"text": text, "format": inputs.get("format", "mp3")}
        if reference_id:
            payload["reference_id"] = reference_id

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self._base_url}/v1/tts",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobRef(status="failed", error=f"Fish Audio {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Fish Audio request failed: {exc}")

        content_type = response.headers.get("content-type", "audio/mpeg")
        return JobRef(
            status="succeeded",
            output={"audio_bytes": response.content, "content_type": content_type},
        )
