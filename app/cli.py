"""Operator commands.

    python -m app.cli setup     # webhook + menu button + commands
    python -m app.cli poll      # local development without a public webhook
    python -m app.cli issues    # payments that need the operator
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime

from .config import Settings
from .llm import make_llm
from .service import Vekil, process_update
from .store import Store
from .telegram import BotAPI

UPDATES = ["message", "pre_checkout_query", "business_connection", "business_message",
           "edited_business_message", "deleted_business_messages"]
COMMANDS = [
    {"command": "start", "description": "Paneli aç ve kurulum adımları"},
    {"command": "paysupport", "description": "Ödeme desteği"},
    {"command": "terms", "description": "Kullanım koşulları"},
]


async def setup(settings: Settings) -> None:
    api = BotAPI(settings.bot_token)
    try:
        me = await api("getMe")
        if not me.get("can_connect_to_business"):
            print("UYARI: BotFather > Bot Settings > Business Mode açık değil. Açmadan işletmeler botu bağlayamaz.")
        await api("setWebhook", url=f"{settings.webapp_url}/telegram/webhook", secret_token=settings.webhook_secret,
                  allowed_updates=UPDATES)
        await api("setChatMenuButton", menu_button={"type": "web_app", "text": "Panel",
                                                    "web_app": {"url": settings.webapp_url}})
        await api("setMyCommands", commands=COMMANDS)
        print(f"@{me['username']} hazır: webhook, Panel butonu ve komutlar ayarlandı.")
    finally:
        await api.close()


async def poll(settings: Settings) -> None:
    api = BotAPI(settings.bot_token)
    llm = make_llm(settings.llm_provider, settings.llm_api_key, settings.llm_model)
    store = Store(settings.db_path)
    service = Vekil(api, llm, settings, store)
    failures: dict[int, int] = {}
    offset = 0
    try:
        if (await api("getWebhookInfo")).get("url"):
            raise SystemExit("Botta webhook ayarlı. Polling için önce deleteWebhook çağır.")
        logging.info("Polling başladı")
        while True:
            try:
                for update in await api("getUpdates", offset=offset, timeout=25, allowed_updates=UPDATES):
                    await process_update(service, update, failures)
                    offset = update["update_id"] + 1
            except Exception as exc:  # noqa: BLE001
                logging.error("Güncelleme işlenemedi: %s; yeniden denenecek", type(exc).__name__)
                await asyncio.sleep(5)
    finally:
        await api.close()
        await llm.close()


def issues(settings: Settings) -> None:
    rows = Store(settings.db_path).open_issues()
    if not rows:
        print("Açık ödeme sorunu yok.")
    for row in rows:
        when = datetime.fromtimestamp(row["created"]).strftime("%Y-%m-%d %H:%M")
        print(f"{when}  {row['reason']:<24} owner={row['owner_id']}  stars={row['stars']}  charge={row['charge']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "poll", "issues"):
        sub.add_parser(name)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    if args.cmd == "setup":
        asyncio.run(setup(settings))
    elif args.cmd == "poll":
        asyncio.run(poll(settings))
    else:
        issues(settings)


if __name__ == "__main__":
    main()
