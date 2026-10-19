"""Async engine, session factory and declarative base."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(settings.db_url, echo=False)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _ensure_sqlite_dir() -> None:
    """Create the parent directory for a file-based SQLite DB if missing."""
    url = make_url(settings.db_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    """Create all tables (MVP: no migrations)."""
    _ensure_sqlite_dir()

    import db.models  # noqa: F401  # register models with Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Close the engine (call on shutdown)."""
    await engine.dispose()
