"""Telegram WebApp initData validation."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from config.settings import settings


def _secret_key(token: str) -> bytes:
    return hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()


def validate_init_data(init_data: str) -> dict[str, str]:
    """Validate Telegram WebApp initData and return its fields."""
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("initData has no hash")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(parsed.items())
    )
    secret = _secret_key(settings.bot_token)
    calculated = hmac.new(
        secret, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("initData hash mismatch")
    return parsed


def telegram_id_from_init_data(init_data: str) -> int:
    """Extract and validate the Telegram user id from initData."""
    data = validate_init_data(init_data)
    user_raw = data.get("user", "{}")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("initData user is not valid JSON") from exc

    telegram_id = user.get("id")
    if not telegram_id:
        raise ValueError("initData has no user id")
    return int(telegram_id)
