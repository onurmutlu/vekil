"""Login for the web panel (outside Telegram).

1. The site shows the Telegram Login Widget; Telegram returns signed user fields.
   https://core.telegram.org/widgets/login#checking-authorization
2. We verify them (secret = SHA256(bot_token)) and issue a short session token,
   HMAC-signed with a key derived from the bot token. No passwords are stored.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time


class AuthError(Exception):
    pass


def sign_login(fields: dict, bot_token: str) -> str:
    """Hash Telegram would attach to these Login Widget fields (used in tests)."""
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields) if k != "hash" and fields[k] is not None)
    return hmac.new(hashlib.sha256(bot_token.encode()).digest(), check.encode(), hashlib.sha256).hexdigest()


def verify_login(fields: dict, bot_token: str, max_age: int = 86400, now: float | None = None) -> dict:
    received = str(fields.get("hash", ""))
    clean = {k: str(v) for k, v in fields.items() if k != "hash" and v is not None}
    if not received or not hmac.compare_digest(sign_login(clean, bot_token), received):
        raise AuthError("Telegram girişi doğrulanamadı")
    try:
        auth_date, user_id = int(clean["auth_date"]), int(clean["id"])
    except (KeyError, ValueError):
        raise AuthError("Eksik giriş bilgisi") from None
    now = time.time() if now is None else now
    if now - auth_date > max_age:
        raise AuthError("Giriş bilgisinin süresi doldu, yeniden giriş yap")
    return {"id": user_id, "first_name": clean.get("first_name", ""), "last_name": clean.get("last_name", "")}


def _key(bot_token: str) -> bytes:
    return hmac.new(b"vekil-session", bot_token.encode(), hashlib.sha256).digest()


def issue_session(user_id: int, bot_token: str, ttl: int = 7 * 86400, now: float | None = None) -> str:
    expires = int((time.time() if now is None else now) + ttl)
    body = f"{user_id}.{expires}"
    sig = base64.urlsafe_b64encode(hmac.new(_key(bot_token), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{body}.{sig}"


def read_session(token: str, bot_token: str, now: float | None = None) -> int:
    try:
        user_id, expires, sig = token.split(".")
        body = f"{user_id}.{expires}"
        expected = base64.urlsafe_b64encode(
            hmac.new(_key(bot_token), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    except ValueError:
        raise AuthError("Oturum geçersiz") from None
    if not hmac.compare_digest(expected, sig):
        raise AuthError("Oturum geçersiz")
    if int(expires) < (time.time() if now is None else now):
        raise AuthError("Oturumun süresi doldu, yeniden giriş yap")
    return int(user_id)
