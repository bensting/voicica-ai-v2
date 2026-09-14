"""Mirrors a succeeded job's output into Cloudflare R2 (ADR 0004).

Fish Audio (and every synchronous provider) returns the media as bytes
directly in the response body — there's no temporary vendor URL to download
from the way there is for Kie, so "mirroring" here is just "upload the bytes
we already have." The async-provider case (download-then-upload from a
short-lived URL) is a later addition when Kie's adapter is built.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.config import Config
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

# Placeholder retention window. Per-capability retention (ADR 0004) is a
# candidate future app_settings value (ADR 0012) once more than one capability
# mirrors assets — not worth a settings row for a single hardcoded number yet.
_DEFAULT_RETENTION_DAYS = 90

# Explicit rather than relying on botocore's own default (also 60/60, as it
# happens — verified, not assumed) — every other outbound call in this
# codebase (providers/*.py's httpx clients) states its timeout in the code
# rather than leaning on a library default nobody's read, and this is the
# one place that wasn't yet consistent with that (found while answering a
# question about worker timeout handling end to end — ADR 0014).
_R2_CLIENT_CONFIG = Config(connect_timeout=30, read_timeout=60, retries={"max_attempts": 2})


def _r2_client():
    settings = get_settings()
    if not (settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise RuntimeError(
            "R2 is not configured — set R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / "
            "R2_SECRET_ACCESS_KEY in .env"
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=_R2_CLIENT_CONFIG,
    )


async def upload_bytes(
    *, job_id: uuid.UUID, data: bytes, content_type: str, extension: str
) -> dict[str, Any]:
    """Uploads `data` to R2 under a job-namespaced key. boto3 is sync, so the
    actual network call runs off the event loop in a threadpool."""
    settings = get_settings()
    key = f"jobs/{job_id}.{extension}"

    def _put() -> None:
        client = _r2_client()
        client.put_object(Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type)

    await run_in_threadpool(_put)

    now = datetime.now(UTC)
    return {
        "r2_key": key,
        "mirror_status": "done",
        "mirrored_at": now,
        "expires_at": now + timedelta(days=_DEFAULT_RETENTION_DAYS),
    }


async def upload_public_bytes(
    *, owner_id: str, data: bytes, content_type: str, extension: str
) -> dict[str, str]:
    """A Kie image-to-image reference upload (ADR 0016) — the one case in
    this codebase where something needs a real, unauthenticated public URL:
    Kie's own servers fetch a job's `input_urls` themselves, and obviously
    can't attach this app's Firebase auth header the way `GET
    /jobs/{id}/asset` requires. Distinct `uploads/` prefix (never `jobs/`,
    which holds generated outputs) so retention/cleanup can differ per
    prefix — the caller deletes this the moment its job reaches any
    terminal state (`services/jobs.py cleanup_kie_uploads`), not kept for
    ADR 0004's 90-day output-retention window.

    Raises `RuntimeError` if `R2_PUBLIC_BASE_URL` isn't configured — a
    silently-broken image-to-image feature (a URL Kie can never actually
    reach) is worse than an explicit failure at the point this is first
    needed."""
    settings = get_settings()
    if not settings.r2_public_base_url:
        raise RuntimeError(
            "R2_PUBLIC_BASE_URL is not configured — image-to-image needs a public "
            "URL Kie's servers can fetch (see ADR 0016); a Cloudflare R2 bucket's "
            "own public dev URL is enough, no custom domain required."
        )
    key = f"uploads/{owner_id}/{uuid.uuid4()}.{extension}"

    def _put() -> None:
        client = _r2_client()
        client.put_object(Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type)

    await run_in_threadpool(_put)
    url = f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    return {"r2_key": key, "url": url}


async def delete_object(r2_key: str) -> None:
    """Best-effort cleanup for a short-lived public upload (ADR 0016) —
    callers log and swallow failures here (same posture as Fish Audio's
    best-effort voice-model delete, `services/voice_models.py`); a cleanup
    failure shouldn't fail or retry the job it belongs to."""
    settings = get_settings()

    def _delete() -> None:
        client = _r2_client()
        client.delete_object(Bucket=settings.r2_bucket, Key=r2_key)

    await run_in_threadpool(_delete)


async def download_bytes(r2_key: str) -> tuple[bytes, str]:
    """Fetches an object's bytes + content-type from R2, for the backend to
    hand to a client itself (`GET /jobs/{id}/asset`) rather than a presigned
    URL: a recent botocore/R2 incompatibility makes presigned GET URLs from
    this environment reject with "Missing x-amz-content-sha256" — they
    require headers a plain `<audio src>`/browser fetch can't attach, which
    defeats the point of presigning. Proxying is the fallback that's actually
    verified working; revisit presigned URLs once that's resolved upstream."""
    settings = get_settings()

    def _get() -> tuple[bytes, str]:
        client = _r2_client()
        obj = client.get_object(Bucket=settings.r2_bucket, Key=r2_key)
        return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")

    return await run_in_threadpool(_get)
