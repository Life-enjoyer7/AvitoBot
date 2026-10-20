"""FastAPI backend for the Telegram Mini App.

Shares the same database and parsers as the bot. Authentication uses Telegram
WebApp initData (validated with the bot token), with an optional dev fallback
(X-User-Id header when `WEBAPP_DEV_MODE=true`).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from db.database import async_session_factory, init_db
from db.repositories import history_repo, track_repo, user_repo
from parser.parser_factory import ParserFactory
from utils.url_validator import (
    UnsupportedMarketplaceError,
    classify_marketplace,
    normalize_url,
)
from web.auth import telegram_id_from_init_data

STATIC_DIR = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="MarketTracker Mini App", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def current_telegram_id(
    init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> int:
    """Dependency: resolve the authenticated Telegram user id."""
    if init_data:
        try:
            return telegram_id_from_init_data(init_data)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid initData") from exc
    if settings.webapp_dev_mode and user_id:
        return int(user_id)
    raise HTTPException(status_code=401, detail="Authentication required")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def _get_user_id(session, telegram_id: int) -> int:
    user = await user_repo.get_or_create_user(session, telegram_id=telegram_id)
    await session.flush()
    return user.id


def _track_payload(track, change_7d: float | None) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "marketplace": track.marketplace.value,
        "url": track.url,
        "current_price": track.current_price,
        "target_price": track.target_price,
        "alert_drop_percent": track.alert_drop_percent,
        "alert_rise_percent": track.alert_rise_percent,
        "is_active": track.is_active,
        "image_url": track.image_url,
        "change_7d": change_7d,
    }


@app.get("/api/me")
async def me(tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        tracks = await track_repo.list_tracks(session, user_id, active_only=True)
        await session.commit()

    last_check = max(
        (t.last_checked_at for t in tracks if t.last_checked_at), default=None
    )
    return {
        "telegram_id": tg_id,
        "track_count": len(tracks),
        "last_check": last_check.isoformat() if last_check else None,
    }


@app.get("/api/tracks")
async def tracks(tg_id: int = Depends(current_telegram_id)) -> list[dict]:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        items = await track_repo.list_tracks(session, user_id)
        result = []
        for track in items:
            first = await history_repo.get_first_price_since(session, track.id, days=7)
            change = None
            if first and track.current_price:
                change = round((track.current_price - first) / first * 100.0, 1)
            result.append(_track_payload(track, change))
        await session.commit()
    return result


@app.post("/api/tracks", status_code=201)
async def add_track(body: dict, tg_id: int = Depends(current_telegram_id)) -> dict:
    raw = (body.get("url") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="URL не указан")

    try:
        url = normalize_url(raw)
        marketplace = classify_marketplace(url)
    except (ValueError, UnsupportedMarketplaceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    listing = await ParserFactory.get_parser(marketplace).parse_listing(url)
    if listing.price is None:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить цену (объявление удалено или недоступно)",
        )

    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.create_track(
            session,
            user_id=user_id,
            marketplace=marketplace,
            url=url,
            title=listing.title or "Без названия",
            current_price=listing.price,
            image_url=listing.image_url,
        )
        if track.current_price is not None:
            await history_repo.add_history(session, track.id, track.current_price)
        await session.commit()

    return {
        "id": track.id,
        "title": track.title,
        "current_price": track.current_price,
        "estimated": listing.estimated,
    }


@app.get("/api/tracks/{track_id}/history")
async def history(track_id: int, tg_id: int = Depends(current_telegram_id)) -> list[dict]:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.get_track(session, track_id, user_id=user_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        items = await history_repo.get_history(session, track_id, limit=30)
        await session.commit()
    return [
        {"price": item.price, "timestamp": item.timestamp.isoformat()}
        for item in items
    ]


@app.patch("/api/tracks/{track_id}")
async def patch_track(track_id: int, body: dict, tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.get_track(session, track_id, user_id=user_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")

        if "target_price" in body:
            value = body["target_price"]
            track.target_price = float(value) if value else None
        if "alert_drop_percent" in body:
            value = body["alert_drop_percent"]
            track.alert_drop_percent = float(value) if value else None
        if "alert_rise_percent" in body:
            value = body["alert_rise_percent"]
            track.alert_rise_percent = float(value) if value else None
        await session.commit()

    return {"ok": True}


@app.post("/api/tracks/{track_id}/stop")
async def stop_track(track_id: int, tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.get_track(session, track_id, user_id=user_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        await track_repo.deactivate_track(session, track)
        await session.commit()
    return {"ok": True}
