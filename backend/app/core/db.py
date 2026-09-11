"""Async SQLAlchemy engine + session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

_settings = get_settings()

# asyncpg doesn't understand libpq-style URL params (sslmode=, channel_binding=)
# the way psycopg does — a managed Postgres's TLS requirement (Neon, ADR 0006)
# has to go through connect_args instead. DATABASE_URL must NOT carry those
# query params; see .env.example.
_connect_args: dict = {"ssl": "require"} if _settings.database_ssl_require else {}

# Neon's pooled endpoint (the "-pooler" hostname .env.example points at) is
# PgBouncer in transaction-pooling mode: each logical connection can land on a
# different physical backend between statements, so asyncpg's default
# server-side prepared-statement cache goes stale — a query that demonstrably
# matches rows can come back empty. Disabling it is Neon's own documented fix
# for asyncpg specifically; harmless (just no prepared-statement reuse) against
# a non-pooled local Postgres too, so it's unconditional rather than another
# settings flag.
_connect_args["statement_cache_size"] = 0

engine = create_async_engine(_settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model (app/models)."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, committed/rolled back around it."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
