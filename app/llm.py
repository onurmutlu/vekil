"""Language-model providers behind one call: `await llm(system, messages) -> str`.

`messages` alternate between {"role": "user"} and {"role": "assistant"}, starting with user.
"""
from __future__ import annotations

import json

import httpx


class LLMError(Exception):
    pass


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None):
        self.api_key, self.model = api_key, model
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(45.0))

    async def __call__(self, system: str, messages: list[dict]) -> str:
        try:
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                json={"model": self.model, "max_tokens": 600, "system": system, "messages": messages},
            )
        except httpx.HTTPError as exc:
            raise LLMError(type(exc).__name__) from None
        if response.status_code != 200:
            raise LLMError(f"anthropic {response.status_code}")
        data = response.json()
        return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")

    async def close(self):
        await self.client.aclose()


class OpenAILLM:
    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient | None = None):
        self.api_key, self.model = api_key, model
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(45.0))

    async def __call__(self, system: str, messages: list[dict]) -> str:
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "max_tokens": 600,
                      "messages": [{"role": "system", "content": system}, *messages]},
            )
        except httpx.HTTPError as exc:
            raise LLMError(type(exc).__name__) from None
        if response.status_code != 200:
            raise LLMError(f"openai {response.status_code}")
        return response.json()["choices"][0]["message"]["content"] or ""

    async def close(self):
        await self.client.aclose()


class EchoLLM:
    """Offline stand-in for development: no API key, predictable answers."""

    async def __call__(self, system: str, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        wants_human = any(w in last.lower() for w in ("insan", "yetkili", "human", "şikayet"))
        return json.dumps({"reply": f"(deneme) Mesajını aldım: {last[:120]}", "handoff": wants_human,
                           "reason": "müşteri yetkili istedi" if wants_human else ""}, ensure_ascii=False)

    async def close(self):
        return None


def make_llm(provider: str, api_key: str, model: str):
    if provider == "anthropic":
        return AnthropicLLM(api_key, model)
    if provider == "openai":
        return OpenAILLM(api_key, model)
    return EchoLLM()
