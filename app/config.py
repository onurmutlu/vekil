"""Settings from the environment."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

SUBSCRIPTION_PERIOD = 2592000  # Telegram Star subscriptions renew every 30 days


class ConfigError(ValueError):
    pass


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    webhook_secret: str
    webapp_url: str
    support_text: str = ""
    terms_text: str = ""
    product_name: str = "Vekil"
    bot_username: str = ""
    # AI
    llm_provider: str = "anthropic"          # anthropic | openai | echo (development only)
    llm_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    # plans
    sales_enabled: bool = False
    trial_replies: int = 50                  # free AI replies per business account, once
    plan_stars: int = 750                    # price of the monthly plan
    plan_replies: int = 2000                 # AI replies per paid 30-day period
    playground_daily: int = 30               # test replies per owner per day in the dashboard
    # safety
    max_replies_per_chat_hour: int = 30      # stops loops with other bots and abuse
    max_message_age: int = 600               # never answer a backlog older than this (seconds)
    history_messages: int = 20
    admin_ids: frozenset[int] = frozenset()
    db_path: str = "data/vekil.sqlite3"
    init_data_max_age: int = 86400

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [k for k in ("BOT_TOKEN", "WEBHOOK_SECRET", "WEBAPP_URL") if not os.getenv(k)]
        if missing:
            raise ConfigError("Eksik ortam değişkeni: " + ", ".join(missing))
        env = os.getenv
        settings = cls(
            bot_token=os.environ["BOT_TOKEN"],
            webhook_secret=os.environ["WEBHOOK_SECRET"],
            webapp_url=os.environ["WEBAPP_URL"].rstrip("/"),
            support_text=env("SUPPORT_TEXT", ""),
            terms_text=env("TERMS_TEXT", ""),
            product_name=env("PRODUCT_NAME", "Vekil"),
            bot_username=env("BOT_USERNAME", "").lstrip("@"),
            llm_provider=env("LLM_PROVIDER", "anthropic").lower(),
            llm_api_key=env("LLM_API_KEY", ""),
            llm_model=env("LLM_MODEL", "claude-haiku-5-5"),
            sales_enabled=_bool(env("SALES_ENABLED")),
            trial_replies=int(env("TRIAL_REPLIES", "50")),
            plan_stars=int(env("PLAN_STARS", "750")),
            plan_replies=int(env("PLAN_REPLIES", "2000")),
            playground_daily=int(env("PLAYGROUND_DAILY", "30")),
            max_replies_per_chat_hour=int(env("MAX_REPLIES_PER_CHAT_HOUR", "30")),
            max_message_age=int(env("MAX_MESSAGE_AGE", "600")),
            history_messages=int(env("HISTORY_MESSAGES", "20")),
            admin_ids=frozenset(int(x) for x in env("ADMIN_IDS", "").replace(" ", "").split(",") if x),
            db_path=env("DB_PATH", "data/vekil.sqlite3"),
        )
        settings.check()
        return settings

    def check(self) -> None:
        if len(self.webhook_secret) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", self.webhook_secret):
            raise ConfigError("WEBHOOK_SECRET en az 32 karakter olmalı (A-Z, a-z, 0-9, _ ve -)")
        if not self.webapp_url.startswith("https://"):
            raise ConfigError("WEBAPP_URL https:// ile başlamalı (Telegram Mini App şartı)")
        if self.llm_provider not in ("anthropic", "openai", "echo"):
            raise ConfigError("LLM_PROVIDER anthropic, openai ya da echo olmalı")
        if self.llm_provider != "echo" and not self.llm_api_key:
            raise ConfigError("LLM_API_KEY gerekli")
        if self.sales_enabled and (not self.support_text or not self.terms_text):
            raise ConfigError("Satış açıkken SUPPORT_TEXT ve TERMS_TEXT zorunlu (/paysupport ve /terms)")
        if self.plan_stars < 1 or self.plan_replies < 1 or self.trial_replies < 0:
            raise ConfigError("Plan değerleri pozitif olmalı")
