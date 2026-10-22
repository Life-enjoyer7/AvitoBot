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
from db.repositories import alert_repo, history_repo, metric_repo, track_repo, user_repo
from parser.parser_factory import ParserFactory
from utils.url_validator import (
    UnsupportedMarketplaceError,
    classify_marketplace,
    ensure_product_url,
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


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/debug/proxy")
async def debug_proxy() -> dict:
    """Diagnostic: show masked proxy config and test it (egress IP)."""
    from utils.proxy_debug import mask_proxy, probe_proxy

    info = await probe_proxy(settings.parser_proxy_url)
    return {"proxy": mask_proxy(settings.parser_proxy_url), **info}


async def _get_user_id(session, telegram_id: int) -> int:
    user = await user_repo.get_or_create_user(session, telegram_id=telegram_id)
    await session.flush()
    return user.id


def _body_float(body: dict, key: str, default: float | None = None) -> float | None:
    if key in body and body[key] not in (None, ""):
        return float(body[key])
    return default


def _track_payload(track, change_7d: float | None, history: list[float]) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "marketplace": track.marketplace.value,
        "url": track.url,
        "current_price": track.current_price,
        "last_checked_price": track.last_checked_price,
        "target_price": track.target_price,
        "alert_drop_percent": track.alert_drop_percent,
        "alert_rise_percent": track.alert_rise_percent,
        "is_active": track.is_active,
        "image_url": track.image_url,
        "change_7d": change_7d,
        "history": history,
    }


@app.get("/api/me")
async def me(tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(session, telegram_id=tg_id)
        await session.flush()
        tracks = await track_repo.list_tracks(session, user.id, active_only=True)
        alerts_count = await alert_repo.count_unread_alerts(session, user.id)
        await session.commit()

    last_check = max(
        (t.last_checked_at for t in tracks if t.last_checked_at), default=None
    )
    return {
        "telegram_id": tg_id,
        "username": user.username,
        "track_count": len(tracks),
        "alerts_count": alerts_count,
        "last_check": last_check.isoformat() if last_check else None,
        "notify_drop": bool(user.notify_drop),
        "notify_rise": bool(user.notify_rise),
        "notify_target": bool(user.notify_target),
        "notify_daily_digest": bool(user.notify_daily_digest),
        "check_interval_minutes": user.check_interval_minutes,
    }


@app.get("/api/metrics")
async def metrics(tg_id: int = Depends(current_telegram_id)) -> dict:
    """Product metrics (5 KPIs) for the dashboard."""
    async with async_session_factory() as session:
        result = await metric_repo.compute_metrics(session)
    return result


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
            hist = await history_repo.get_history(session, track.id, limit=12)
            result.append(_track_payload(track, change, [h.price for h in hist]))
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
        ensure_product_url(url, marketplace)
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
            alert_drop_percent=_body_float(body, "alert_drop_percent", 5.0),
            alert_rise_percent=_body_float(body, "alert_rise_percent"),
            target_price=_body_float(body, "target_price"),
        )
        if track.current_price is not None:
            await history_repo.add_history(session, track.id, track.current_price)
        await metric_repo.record_event(
            session,
            "parse_ok" if not listing.estimated else "parse_fail",
            user_id=user_id,
            marketplace=marketplace.value,
        )
        await session.commit()

    return {
        "id": track.id,
        "title": track.title,
        "current_price": track.current_price,
        "estimated": listing.estimated,
    }


@app.get("/api/alerts")
async def alerts(tg_id: int = Depends(current_telegram_id)) -> list[dict]:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        rows = await alert_repo.list_alerts_for_user(session, user_id, limit=30)
        await session.commit()

    return [
        {
            "id": alert.id,
            "track_id": alert.track_id,
            "title": title,
            "alert_type": alert.alert_type.value,
            "old_price": alert.old_price,
            "new_price": alert.new_price,
            "sent_at": alert.sent_at.isoformat(),
        }
        for alert, title in rows
    ]


@app.get("/api/tracks/{track_id}/history")
async def history(track_id: int, days: int = 30, tg_id: int = Depends(current_telegram_id)) -> list[dict]:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.get_track(session, track_id, user_id=user_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        items = await history_repo.get_history_since(session, track_id, days=days)
        if not items:
            items = await history_repo.get_history(session, track_id, limit=30)
        # Метрика вовлечённости: пользователь открыл график/историю.
        await metric_repo.record_event(
            session, "history_view", user_id=user_id, track_id=track_id, marketplace=track.marketplace.value
        )
        await session.commit()
    return [
        {"price": item.price, "timestamp": item.timestamp.isoformat()}
        for item in items
    ]


@app.post("/api/alerts/read-all")
async def read_all_alerts(tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        await alert_repo.delete_all_alerts(session, user_id)
        await session.commit()
    return {"ok": True}


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
        if "is_active" in body:
            track.is_active = bool(body["is_active"])
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


@app.delete("/api/tracks/{track_id}")
async def delete_track(track_id: int, tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user_id = await _get_user_id(session, tg_id)
        track = await track_repo.get_track(session, track_id, user_id=user_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        await session.delete(track)
        await session.commit()
    return {"ok": True}


@app.patch("/api/settings")
async def patch_settings(body: dict, tg_id: int = Depends(current_telegram_id)) -> dict:
    async with async_session_factory() as session:
        user = await user_repo.get_or_create_user(session, telegram_id=tg_id)
        if "notify_drop" in body:
            user.notify_drop = bool(body["notify_drop"])
        if "notify_rise" in body:
            user.notify_rise = bool(body["notify_rise"])
        if "notify_target" in body:
            user.notify_target = bool(body["notify_target"])
        if "check_interval_minutes" in body:
            value = int(body["check_interval_minutes"])
            if value not in (5, 10, 15, 20, 30):
                raise HTTPException(status_code=400, detail="Допустимая частота: 5, 10, 15, 20, 30 минут")
            user.check_interval_minutes = value
        if "notify_daily_digest" in body:
            user.notify_daily_digest = bool(body["notify_daily_digest"])
        await session.commit()
    return {"ok": True}

