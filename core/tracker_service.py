"""Alert evaluation logic (pure business rules)."""

from __future__ import annotations

from db.enums import AlertType
from db.models import Track
from utils.formatting import format_price


def detect_alert(track: Track, new_price: float | None) -> AlertType | None:
    """Return the alert that should fire, or None.

    Priority: REMOVED > TARGET > DROP > RISE.
    Percent changes are computed against `track.last_checked_price`.
    """
    if new_price is None:
        return AlertType.REMOVED

    if track.target_price is not None and new_price <= track.target_price:
        return AlertType.TARGET

    previous = track.last_checked_price
    if previous is not None and previous > 0:
        if track.alert_drop_percent is not None:
            drop = (previous - new_price) / previous * 100.0
            if drop >= track.alert_drop_percent:
                return AlertType.DROP
        if track.alert_rise_percent is not None:
            rise = (new_price - previous) / previous * 100.0
            if rise >= track.alert_rise_percent:
                return AlertType.RISE

    return None


def user_wants_alert(user, alert_type: AlertType) -> bool:
    """Return True if the user enabled this alert type in global settings."""
    if alert_type == AlertType.DROP:
        return bool(getattr(user, "notify_drop", True))
    if alert_type == AlertType.RISE:
        return bool(getattr(user, "notify_rise", True))
    if alert_type == AlertType.TARGET:
        return bool(getattr(user, "notify_target", True))
    return True  # REMOVED и прочие — всегда


def build_alert_message(
    track: Track,
    alert_type: AlertType,
    old_price: float | None,
    new_price: float | None,
) -> str:
    """Build the HTML notification text for a fired alert."""
    header = f"<b>{track.title}</b>\n🏪 {track.marketplace.value}\n"

    if alert_type is AlertType.TARGET:
        body = (
            f"🎯 Достигнута целевая цена!\n"
            f"Цена: <b>{format_price(new_price)}</b>"
            f" (цель: {format_price(track.target_price)})"
        )
    elif alert_type is AlertType.DROP:
        pct = _percent_change(old_price, new_price)
        body = (
            f"📉 Цена упала на <b>{pct}%</b>!\n"
            f"Было: {format_price(old_price)} → Стало: <b>{format_price(new_price)}</b>"
        )
    elif alert_type is AlertType.RISE:
        pct = _percent_change(old_price, new_price)
        body = (
            f"📈 Цена выросла на <b>{pct}%</b>!\n"
            f"Было: {format_price(old_price)} → Стало: <b>{format_price(new_price)}</b>"
        )
    else:  # REMOVED
        body = (
            "⚠️ Объявление снято с продажи или товар закончился.\n"
            "Отслеживание остановлено."
        )

    return f"{header}{body}"


def _percent_change(old: float | None, new: float | None) -> str:
    if old is None or old == 0:
        return "—"
    return f"{(new - old) / old * 100:.1f}"
