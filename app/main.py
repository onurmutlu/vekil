"""FastAPI app: owner dashboard (Mini App), its API and the Telegram webhook."""
from __future__ import annotations

import contextlib
import hmac
import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import initdata
from .config import Settings
from .llm import make_llm
from .service import ServiceError, Vekil, process_update
from .store import Store
from .telegram import BotAPI, TelegramError

log = logging.getLogger("vekil")
WEBAPP_DIR = Path(__file__).resolve().parents[1] / "webapp"


class Profile(BaseModel):
    business_name: str = Field("", max_length=64)
    about: str = Field("", max_length=1000)
    knowledge: str = Field("", max_length=8000)
    tone: str = Field("", max_length=300)
    handoff_note: str = Field("", max_length=500)
    pause_minutes: int = Field(30, ge=1, le=1440)


class Toggle(BaseModel):
    active: bool


class PlaygroundMessage(BaseModel):
    from_: str = Field(alias="from", pattern="^(customer|assistant)$")
    text: str = Field(min_length=1, max_length=1000)


class Playground(BaseModel):
    messages: list[PlaygroundMessage] = Field(min_length=1, max_length=20)


def create_app(settings: Settings | None = None, store: Store | None = None, api=None, llm=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.db_path)
    own_api, own_llm = api is None, llm is None
    api = api or BotAPI(settings.bot_token)
    llm = llm or make_llm(settings.llm_provider, settings.llm_api_key, settings.llm_model)
    service = Vekil(api, llm, settings, store)
    failures: dict[int, int] = {}

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if own_api:
                await api.close()
            if own_llm:
                await llm.close()

    app = FastAPI(title=settings.product_name, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service

    def owner(init_data: str | None) -> int:
        try:
            user = initdata.validate(init_data or "", settings.bot_token, settings.init_data_max_age)
        except initdata.InvalidInitData:
            raise HTTPException(401, "Telegram oturumu doğrulanamadı. Paneli bot üzerinden yeniden aç.") from None
        name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
        store.ensure_account(user["id"], name)
        return user["id"]

    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/me")
    async def me(x_telegram_init_data: str | None = Header(None)):
        return service.view(owner(x_telegram_init_data))

    @app.put("/api/profile")
    async def update_profile(body: Profile, x_telegram_init_data: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data)
        store.update_profile(owner_id, body.model_dump())
        return service.view(owner_id)

    @app.post("/api/active")
    async def set_active(body: Toggle, x_telegram_init_data: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data)
        service.set_active(owner_id, body.active)
        return service.view(owner_id)

    @app.get("/api/chats")
    async def chats(x_telegram_init_data: str | None = Header(None)):
        return service.chats(owner(x_telegram_init_data))

    @app.post("/api/chats/{chat_id}/resume")
    async def resume(chat_id: int, x_telegram_init_data: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data)
        service.resume(owner_id, chat_id)
        return service.chats(owner_id)

    @app.post("/api/playground")
    async def playground(body: Playground, x_telegram_init_data: str | None = Header(None)):
        messages = [{"from": m.from_, "text": m.text} for m in body.messages]
        return await service.playground(owner(x_telegram_init_data), messages)

    @app.post("/api/billing/invoice")
    async def invoice(x_telegram_init_data: str | None = Header(None)):
        try:
            return await service.plan_invoice(owner(x_telegram_init_data))
        except TelegramError as exc:
            log.error("Fatura oluşturulamadı: %s", exc.description)
            raise HTTPException(502, "Ödeme bağlantısı oluşturulamadı, biraz sonra tekrar dene.") from None

    @app.post("/telegram/webhook")
    async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
        if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", settings.webhook_secret):
            raise HTTPException(403)
        try:
            await process_update(service, await request.json(), failures)
        except Exception:
            raise HTTPException(500) from None  # Telegram redelivers
        return {"ok": True}

    @app.get("/")
    async def index():
        return FileResponse(WEBAPP_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")
    return app


def app() -> FastAPI:  # `uvicorn app.main:app --factory`
    logging.basicConfig(level=logging.INFO)
    return create_app()
