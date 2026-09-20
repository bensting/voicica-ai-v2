"""Application settings.

All secrets/environment-specific values come from env vars (see ../../.env.example).
Nothing here is a business-tunable value — those live in `app_settings`
(the database table, ADR 0012), read via `services.settings`, not here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (ADR 0006). Neon (and most managed Postgres) requires TLS; a
    # local Docker Postgres for dev doesn't have it configured at all — hence
    # this being a separate, explicit switch rather than inferred from the URL.
    database_url: str = "postgresql+asyncpg://voicica:voicica@localhost:5432/voicica"
    database_ssl_require: bool = False
    # ADR 0026 — the job dispatcher's single LISTEN connection needs a real,
    # non-pooled connection: verified live against Neon that LISTEN/NOTIFY
    # silently doesn't work over its pooler endpoint (a notification sent on
    # one pooled connection never reaches a listener on another, since the
    # pooler can hand out a different backend connection per transaction —
    # there's nothing to "fail" on, so this isn't a bug that throws, it's a
    # notification that just never arrives). Falls back to `database_url`
    # for local dev against a plain, unpooled Postgres, where the
    # distinction doesn't exist. Plain `asyncpg` DSN format (no `+asyncpg`
    # driver prefix) — this one connects via raw asyncpg, not SQLAlchemy.
    database_direct_url: str | None = None

    # Auth (ADR 0008) — Firebase Admin SDK service account, as a path to the JSON
    # key file or the JSON itself. core/auth.py is the only place that reads this.
    firebase_credentials_path: str | None = None
    firebase_credentials_json: str | None = None

    # Providers
    fish_audio_api_key: str | None = None
    fish_audio_base_url: str = "https://api.fish.audio"

    # Azure Speech (Cognitive Services) — key is scoped to one region; the
    # endpoint itself is `https://{region}.tts.speech.microsoft.com/...`, so
    # the region is required, not just an optional override.
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None

    # Google Cloud Text-to-Speech. An API key is enough for this API (unlike
    # Firebase Admin, which needs a service account) — verified directly
    # against texttospeech.googleapis.com.
    google_tts_api_key: str | None = None

    # Kie (ADR 0015) — wholesale model-catalog gateway (image/video/music).
    kie_api_key: str | None = None
    kie_base_url: str = "https://api.kie.ai"
    # This backend's own publicly reachable URL, used only to build Kie's
    # callBackUrl at submission time (e.g. "https://api.example.com"). None
    # in local dev — there's nothing public for Kie to call back to, so
    # providers/kie.py simply omits callBackUrl and completion is picked up
    # by the poll-based cron sweep instead (worker/cron.py) — the webhook is
    # the primary path once this is set, never a hard requirement.
    public_base_url: str | None = None

    # Redis (ADR 0014) — the arq task queue behind background job execution.
    # A local, unauthenticated default so a fresh checkout at least imports
    # cleanly; real generation needs a real reachable Redis (see .env.example).
    redis_url: str = "redis://localhost:6379/0"

    # Asset storage (ADR 0004) — Cloudflare R2, S3-compatible.
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "voicica-assets"
    r2_public_base_url: str | None = None  # e.g. a custom domain fronting the bucket

    # CORS — frontend/web's origin(s) during local dev
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    # The one frontend origin to redirect a real browser back to after it
    # leaves this backend's own domain — Stripe Checkout's success/cancel
    # URLs (ADR 0024) today, the only such case so far. Deliberately a
    # separate setting from `cors_allow_origins` (that's an *allow-list*,
    # which can hold more than one real origin — www vs. apex, ADR 0023 —
    # so `[0]` isn't a safe stand-in for "the" frontend URL) and from
    # `public_base_url` (this backend's own URL, not the frontend's).
    frontend_base_url: str = "http://localhost:3000"

    # Stripe (ADR 0024) — one-time credit-pack purchases via a hosted
    # Checkout Session. `stripe_webhook_secret` is per-endpoint (Stripe
    # generates a distinct one for the CLI/local listener vs. each real
    # webhook endpoint registered in the Dashboard) — copying the wrong one
    # across environments makes every webhook 400 on signature verification,
    # the same class of "differs by environment" mistake `CORS_ALLOW_ORIGINS`
    # and `PUBLIC_BASE_URL` already are (backend/README.md's Deploy table).
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
