"""Minimal Bot API client. Never puts the token in logs or exception text."""
from __future__ import annotations

import httpx


class TelegramError(Exception):
    def __init__(self, method: str, code: int | None, description: str, retry_after: int = 0):
        super().__init__(f"Telegram {method} başarısız ({code}): {description}")
        self.method, self.code, self.description, self.retry_after = method, code, description, retry_after


class BotAPI:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None,
                 base_url: str = "https://api.telegram.org"):
        self._url = f"{base_url}/bot{token}/"
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(40.0))

    async def __call__(self, method: str, **payload):
        try:
            response = await self._client.post(self._url + method, json=payload)
        except httpx.HTTPError as exc:
            # str(exc) may contain the URL, which contains the token.
            raise TelegramError(method, None, type(exc).__name__) from None
        try:
            data = response.json()
        except ValueError:
            raise TelegramError(method, response.status_code, "geçersiz yanıt") from None
        if not data.get("ok"):
            raise TelegramError(method, data.get("error_code"), data.get("description", ""),
                                data.get("parameters", {}).get("retry_after", 0))
        return data["result"]

    async def close(self) -> None:
        await self._client.aclose()
