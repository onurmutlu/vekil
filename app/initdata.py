"""Validation of Telegram Mini App initData.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
The Mini App sends `Telegram.WebApp.initData` in the X-Telegram-Init-Data header;
the server never trusts `initDataUnsafe` from the client.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(Exception):
    pass


def _secret(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign(fields: dict[str, str], bot_token: str) -> str:
    """Compute the hash Telegram would send for these fields (used in tests)."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    return hmac.new(_secret(bot_token), check.encode(), hashlib.sha256).hexdigest()


def validate(init_data: str, bot_token: str, max_age: int = 86400, now: float | None = None) -> dict:
    """Return the Telegram user dict, or raise InvalidInitData."""
    if not init_data:
        raise InvalidInitData("initData yok")
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InvalidInitData("initData çözülemedi") from exc
    received = fields.pop("hash", "")
    if not received or not hmac.compare_digest(sign(fields, bot_token), received):
        raise InvalidInitData("imza geçersiz")
    try:
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
        user_id = int(user["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidInitData("kullanıcı bilgisi eksik") from exc
    now = time.time() if now is None else now
    if max_age and now - auth_date > max_age:
        raise InvalidInitData("initData süresi doldu")
    user["id"] = user_id
    return user
