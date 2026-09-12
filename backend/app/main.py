"""FastAPI entrypoint. Routing + input validation only — business logic lives
in services/, provider calls live in providers/ (ADR 0001)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_admin,
    routes_catalog,
    routes_config,
    routes_gallery,
    routes_jobs,
    routes_me,
    routes_tts,
    routes_voice_models,
)
from app.api.errors import register_error_handlers
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="AI Voice Labs v2 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(routes_me.router)
app.include_router(routes_tts.router)
app.include_router(routes_voice_models.router)
app.include_router(routes_jobs.router)
app.include_router(routes_gallery.router)
app.include_router(routes_catalog.router)
app.include_router(routes_config.router)
app.include_router(routes_admin.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
