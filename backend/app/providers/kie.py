"""Kie adapter — a generic, config-driven gateway to Kie's model marketplace
(ADR 0001, ADR 0015). Unlike every other adapter in this codebase, this one
has zero per-model logic: `submit()`/`poll()` never branch on which Kie
model they're given — `model_id` and its input schema/pricing live entirely
in `kie_categories`/`kie_models` (services/kie_catalog.py), never here.

Verified directly against Kie's real API (2026-09-12, both by inspecting
`docs.kie.ai`'s get-task-detail page and by reading a real model's own
"API" tab on kie.ai — not guessed):

- **Submission**: `POST /api/v1/jobs/createTask`, bearer auth, body
  `{"model": "<opaque string>", "callBackUrl": "...", "input": {<opaque
  object>}}` -> `{"code": 200, "data": {"taskId": "..."}}`. One endpoint for
  every model, regardless of vendor (confirmed against two independent
  model families — Flux-2 and GPT Image 2.5 — both use it identically).
  `callBackUrl` is omitted when this backend has no public URL to give Kie
  (local dev) — the poll-based cron sweep (worker/cron.py) is always a
  valid fallback, so this is never a hard requirement, just the primary
  path (architecture.md §3d).
- **Polling**: `GET /api/v1/jobs/recordInfo?taskId=...`, bearer auth,
  returns `state` as one of `waiting`/`queuing`/`generating`/`success`/
  `fail`, plus `resultJson` (a JSON *string* containing `resultUrls`) and
  `creditsConsumed` once terminal.
- Always returns a `processing` `JobRef` from `submit()` (ADR 0014's
  kie-submit task only ever calls this, never waits for a terminal state)
  — this is what makes Kie's adapter genuinely asynchronous, unlike every
  synchronous TTS provider's `submit()`.
"""

import json
from typing import Any

import httpx

from app.providers.base import JobRef, JobStatus, Provider

_STATE_MAP: dict[str, str] = {
    "waiting": "processing",
    "queuing": "processing",
    "generating": "processing",
    "success": "succeeded",
    "fail": "failed",
}


class KieProvider(Provider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.kie.ai",
        callback_base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        # This backend's own public URL, if one is configured (core/config.py
        # public_base_url) — None in local dev, where Kie has nothing to call
        # back to; see module docstring.
        self._callback_base_url = callback_base_url.rstrip("/") if callback_base_url else None

    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        model_id = inputs["model_id"]
        payload: dict[str, Any] = {"model": model_id, "input": inputs["input"]}
        if self._callback_base_url:
            payload["callBackUrl"] = f"{self._callback_base_url}/webhooks/kie"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/jobs/createTask",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobRef(status="failed", error=f"Kie {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobRef(status="failed", error=f"Kie request failed: {exc}")

        body = response.json()
        if body.get("code") != 200:
            return JobRef(status="failed", error=f"Kie {body.get('code')}: {body.get('msg')}")

        task_id = body["data"]["taskId"]
        return JobRef(status="processing", provider_job_id=task_id, provider_state="waiting")

    async def poll(self, provider_job_id: str) -> JobStatus:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/jobs/recordInfo",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    params={"taskId": provider_job_id},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return JobStatus(status="failed", error=f"Kie {exc.response.status_code}: {body}")
        except httpx.HTTPError as exc:
            return JobStatus(status="failed", error=f"Kie request failed: {exc}")

        data = response.json()["data"]
        state = data.get("state")
        canonical = _STATE_MAP.get(state, "processing")

        if canonical == "succeeded":
            result_json = data.get("resultJson")
            result_urls: list[str] = []
            if result_json:
                # Documented as a JSON *string*, not a nested object —
                # verified against docs.kie.ai's get-task-detail example.
                result_urls = json.loads(result_json).get("resultUrls", [])
            return JobStatus(
                status="succeeded",
                provider_state=state,
                output={"result_urls": result_urls, "credits_consumed": data.get("creditsConsumed")},
            )
        if canonical == "failed":
            error = data.get("failMsg") or f"Kie task failed (failCode={data.get('failCode')})"
            return JobStatus(status="failed", provider_state=state, error=error)
        return JobStatus(status="processing", provider_state=state)
