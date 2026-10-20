"""Rich /start welcome message (stats + latest track preview)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import history_repo, track_repo
from utils.formatting import format_price

_INTRO = (
    "🛒 <b>Цены под контролем</b>\n\n"
    "Привет! Я слежу за ценами на Авито, Яндекс Маркете, Ozon, Wildberries "
    "и Auto.ru и присылаю уведомления, когда цена падает.\n\n"
    "Просто добавьте ссылку на товар — я позабочусь об остальном."
)


def _fmt_time(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "—"


async def build_welcome(session: AsyncSession, user_id: int) -> tuple[str, str | None]:
    """Build the rich /start message and the latest track image (if any)."""
    tracks = await track_repo.list_tracks(session, user_id, active_only=True)

    lines = [_INTRO, ""]
    lines.append(f"📦 На отслеживании: <b>{len(tracks)}</b>")

    last_check = max(
        (t.last_checked_at for t in tracks if t.last_checked_at), default=None
    )
    if last_check:
        lines.append(f"🕒 Последняя проверка: <b>{_fmt_time(last_check)}</b>")

    image_url: str | None = None
    if tracks:
        track = tracks[-1]
        image_url = track.image_url
        lines += ["", f"<b>{track.title[:70]}</b>"]
        row = f"🏪 {track.marketplace.value} · 💰 {format_price(track.current_price)}"
        if track.target_price is not None:
            row += f" · 🎯 {format_price(track.target_price)}"
        lines.append(row)

        first = await history_repo.get_first_price_since(session, track.id, days=7)
        if first and track.current_price:
            change = (track.current_price - first) / first * 100.0
            arrow = "📉" if change < 0 else ("📈" if change > 0 else "➡️")
            lines.append(f"{arrow} {change:+.1f}% за 7 дней")

    lines += ["", "Пришлите ссылку на объявление или нажмите «➕ Добавить товар»."]
    return "\n".join(lines), image_url
