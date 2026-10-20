"""Application settings.

Central configuration object loaded from environment variables and,
optionally, a `.env` file located in the project root.

Uses `pydantic-settings` so that every value is validated and typed at
startup. Field names are matched to env vars case-insensitively
(`bot_token` <-> `BOT_TOKEN`).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the `config/` package.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """MarketTracker configuration."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(
        default="",
        description="Telegram bot token from @BotFather (required at startup)",
    )

    # --- Database ---
    db_url: str = Field(
        default="sqlite+aiosqlite:///data/market_tracker.db",
        validation_alias=AliasChoices("db_url", "database_url"),
        description="SQLAlchemy async database URL (DB_URL or Render's DATABASE_URL)",
    )

    # --- Scheduler ---
    scheduler_interval_minutes: int = Field(
        default=15,
        ge=1,
        description="How often the background price-check job runs",
    )

    # --- HTTP client (parsers) ---
    request_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        description="httpx request timeout in seconds",
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        description="User-Agent header used by parsers",
    )
    parser_proxy_url: str | None = Field(
        default=None,
        description=(
            "HTTP/HTTPS proxy for parsers (e.g. http://user:pass@host:port). "
            "Required to bypass marketplace IP blocks from datacenter servers."
        ),
    )
    telegram_proxy_url: str | None = Field(
        default=None,
        description=(
            "Proxy for the Telegram API (http://... or socks5://...). "
            "Needed when api.telegram.org is blocked/throttled by the ISP."
        ),
    )

    # --- Web app (Telegram Mini App) ---
    webapp_host: str = Field(default="127.0.0.1", description="Mini App bind host")
    webapp_port: int = Field(default=8000, description="Mini App port")
    webapp_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("webapp_url", "render_external_url"),
        description="Public HTTPS URL of the Mini App (WEBAPP_URL or Render's RENDER_EXTERNAL_URL)",
    )
    webapp_dev_mode: bool = Field(
        default=False,
        description="Allow X-User-Id auth without Telegram initData (dev only)",
    )
    webapp_dev_user_id: int = Field(
        default=0,
        description="Fallback user id used by the frontend in dev mode",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Minimum console log level")
    log_dir: Path = Field(
        default=BASE_DIR / "logs",
        description="Directory where rotated log files are stored",
    )
    log_rotation: str = Field(default="10 MB", description="Loguru rotation size")
    log_retention: str = Field(default="7 days", description="Loguru retention period")

    # --- Alerts ---
    alert_cooldown_hours: int = Field(
        default=24,
        ge=1,
        description="Minimum hours between repeated alerts for the same track",
    )

    # --- Cloud keep-alive ---
    keep_alive: bool = Field(
        default=False,
        description="Self-ping the Mini App URL so Render's free tier does not sleep",
    )

    @model_validator(mode="after")
    def _normalize_db_url(self) -> "Settings":
        """Rewrite postgres://… to postgresql+asyncpg://… for SQLAlchemy async."""
        raw = self.db_url
        if raw.startswith("postgres://"):
            self.db_url = "postgresql+asyncpg://" + raw[len("postgres://"):]
        elif raw.startswith("postgresql://"):
            self.db_url = "postgresql+asyncpg://" + raw[len("postgresql://"):]
        return self


# Singleton used across the whole application.
settings = Settings()
