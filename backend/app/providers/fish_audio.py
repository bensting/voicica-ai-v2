"""Fish Audio adapter — TTS, and voice cloning (ADR 0009).

Verified against https://docs.fish.audio/api-reference/introduction
(see architecture.md §3e):
- `POST /v1/tts` is synchronous — it streams audio directly in the response.
  `submit()` therefore always returns an already-terminal `JobRef`.
- Voice cloning (`POST /model`) trains a reusable voice. architecture.md's
  original note assumed this needed polling (Kie-style, `state`
  created/training/trained/failed) — **corrected after testing the real
  API**: with `train_mode="fast"` (the only mode this adapter uses — "full"
  mode's timing isn't verified, so isn't exposed), the create call itself
  returns `state: "trained"` already, synchronously, in the same response.
  Training is therefore just as synchronous as TTS here — no poll() needed.
  The resulting model's `_id` is then usable immediately as `reference_id`
  in an ordinary `/v1/tts` call (verified: trained a real test model, spoke
  with it right away, deleted it — see `backend/README.md`).
"""

from typing import Any

import httpx

from app.providers.base import JobRef, Provider


class FishAudioProvider(Provider):
    def __init__(self, api_key: str, base_url: str = "https://api.fish.audio") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        if capability == "tts":
            return await self._synthesize(inputs)
        if capability == "voice_model_training":
            return await self._train(inputs)
        raise ValueError(f"FishAudioProvider doesn't support capability={capability!r}")

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

        # speed/volume: one provider-agnostic scale (schemas.TTSRequest,
        # docstring on services/jobs.py's submit_tts), converted to Fish
        # Audio's own `prosody` shape — ported from the prior project's
        # verified conversion. No pitch support here (verified: no such
        # parameter in Fish Audio's API), silently ignored rather than
        # erroring — the other two providers cover pitch. Only sent when it
        # differs from default, matching the prior project (an explicit
        # prosody object isn't assumed to be a harmless no-op at 1.0/50).
        speed = inputs.get("speed", 1.0)
        volume = inputs.get("volume", 50)
        prosody: dict[str, float] = {}
        if speed != 1.0:
            prosody["speed"] = speed
        if volume != 50:
            prosody["volume"] = (volume - 50) / 50
        if prosody:
            payload["prosody"] = prosody

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

    async def _train(self, inputs: dict[str, Any]) -> JobRef:
        """`POST /model`, multipart — field names verified against the real
        API (`voices` for the sample audio, `texts` for its transcript,
        `type: "tts"` marks it as a speech model, `visibility: "private"`
        since a user's clone shouldn't show up in Fish's own public
        library). `train_mode: "fast"` is hardcoded, not user-facing (see
        module docstring) — it's what makes this call synchronous."""
        title = inputs["title"]
        audio_bytes: bytes = inputs["audio_bytes"]
        audio_filename: str = inputs.get("audio_filename") or "sample.mp3"
        reference_text = inputs.get("reference_text")

        data: dict[str, Any] = {
            "visibility": "private",
            "type": "tts",
            "title": title,
            "train_mode": "fast",
        }
        if reference_text:
            data["texts"] = reference_text
        files = {"voices": (audio_filename, audio_bytes, "audio/mpeg")}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self._base_url}/model",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files=files,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobRef(status="failed", error=f"Fish Audio {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Fish Audio request failed: {exc}")

        model = response.json()
        return JobRef(
            status="succeeded",
            provider_job_id=model["_id"],
            provider_state=model.get("state"),
            output={"provider_model_id": model["_id"], "state": model.get("state")},
        )

    async def delete_voice_model(self, provider_model_id: str) -> None:
        """`DELETE /model/{id}` — called when a user deletes their own
        cloned voice (services/voice_models.py, best-effort there — a
        failure here doesn't block the local row from being removed, same
        as the prior project's own comment on this). Verified against the
        real API (create -> use -> delete round trip)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(
                f"{self._base_url}/model/{provider_model_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
