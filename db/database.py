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


def _migrate_columns(sync_conn) -> None:
    """Lightweight SQLite migration: add new nullable columns if missing."""
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    if "tracks" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("tracks")}
        if "image_url" not in columns:
            sync_conn.execute(text("ALTER TABLE tracks ADD COLUMN image_url VARCHAR(2048)"))


async def init_db() -> None:
    """Create all tables and apply lightweight schema migrations."""
    _ensure_sqlite_dir()

    import db.models  # noqa: F401  # register models with Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_columns)


async def dispose_db() -> None:
    """Close the engine (call on shutdown)."""
    await engine.dispose()
