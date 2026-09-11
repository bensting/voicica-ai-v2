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

    # Asset storage (ADR 0004) — Cloudflare R2, S3-compatible.
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "voicica-assets"
    r2_public_base_url: str | None = None  # e.g. a custom domain fronting the bucket

    # CORS — frontend/web's origin(s) during local dev
    cors_allow_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
