"""SQLAlchemy 2.x ORM models (declarative, typed)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base
from db.enums import AlertType, Marketplace


class User(Base):
    """A Telegram user who tracks listings."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    tracks: Mapped[list[Track]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Track(Base):
    """A single tracked listing with its alert rules."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    marketplace: Mapped[Marketplace] = mapped_column(
        Enum(Marketplace, native_enum=False, length=16), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Price observed on the previous check; used to compute drop/rise percent.
    last_checked_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_drop_percent: Mapped[float | None] = mapped_column(Float, default=5.0, nullable=True)
    alert_rise_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="tracks")
    history: Mapped[list[PriceHistory]] = relationship(
        back_populates="track",
        cascade="all, delete-orphan",
        order_by="PriceHistory.timestamp",
    )
    alerts: Mapped[list[AlertLog]] = relationship(
        back_populates="track",
        cascade="all, delete-orphan",
    )


class PriceHistory(Base):
    """One price observation for a track."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    track: Mapped[Track] = relationship(back_populates="history")


class AlertLog(Base):
    """A record of a sent alert (also used for the 24h cooldown check)."""

    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, native_enum=False, length=16), nullable=False
    )
    old_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    track: Mapped[Track] = relationship(back_populates="alerts")
