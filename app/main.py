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

from . import initdata, webauth
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


class TelegramLogin(BaseModel):
    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


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

    def owner(init_data: str | None, authorization: str | None = None) -> int:
        """Inside Telegram: Mini App initData. On the web: a session from Telegram Login."""
        if init_data:
            try:
                user = initdata.validate(init_data, settings.bot_token, settings.init_data_max_age)
            except initdata.InvalidInitData:
                raise HTTPException(401, "Telegram oturumu doğrulanamadı. Paneli yeniden aç.") from None
            name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
            store.ensure_account(user["id"], name)
            return user["id"]
        if authorization and authorization.startswith("Bearer "):
            try:
                user_id = webauth.read_session(authorization[7:], settings.bot_token)
            except webauth.AuthError as exc:
                raise HTTPException(401, str(exc)) from None
            store.ensure_account(user_id)
            return user_id
        raise HTTPException(401, "Giriş yapman gerekiyor.")

    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/public")
    async def public():
        return {"product_name": settings.product_name, "bot_username": settings.bot_username,
                "trial_replies": settings.trial_replies, "plan_stars": settings.plan_stars,
                "plan_replies": settings.plan_replies, "sales_enabled": settings.sales_enabled}

    @app.post("/api/auth/telegram")
    async def telegram_login(body: TelegramLogin):
        try:
            user = webauth.verify_login(body.model_dump(), settings.bot_token)
        except webauth.AuthError as exc:
            raise HTTPException(401, str(exc)) from None
        store.ensure_account(user["id"], " ".join(x for x in (user["first_name"], user["last_name"]) if x))
        return {"token": webauth.issue_session(user["id"], settings.bot_token)}

    @app.get("/api/me")
    async def me(x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        return service.view(owner(x_telegram_init_data, authorization))

    @app.put("/api/profile")
    async def update_profile(body: Profile, x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data, authorization)
        store.update_profile(owner_id, body.model_dump())
        return service.view(owner_id)

    @app.post("/api/active")
    async def set_active(body: Toggle, x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data, authorization)
        service.set_active(owner_id, body.active)
        return service.view(owner_id)

    @app.get("/api/chats")
    async def chats(x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        return service.chats(owner(x_telegram_init_data, authorization))

    @app.post("/api/chats/{chat_id}/resume")
    async def resume(chat_id: int, x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        owner_id = owner(x_telegram_init_data, authorization)
        service.resume(owner_id, chat_id)
        return service.chats(owner_id)

    @app.post("/api/playground")
    async def playground(body: Playground, x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        messages = [{"from": m.from_, "text": m.text} for m in body.messages]
        return await service.playground(owner(x_telegram_init_data, authorization), messages)

    @app.post("/api/billing/invoice")
    async def invoice(x_telegram_init_data: str | None = Header(None),
                    authorization: str | None = Header(None)):
        try:
            return await service.plan_invoice(owner(x_telegram_init_data, authorization))
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
    async def site():
        return FileResponse(WEBAPP_DIR / "site.html", headers={"Cache-Control": "no-cache"})

    @app.get("/app")
    @app.get("/panel")
    async def panel():
        return FileResponse(WEBAPP_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")
    return app


def app() -> FastAPI:  # `uvicorn app.main:app --factory`
    logging.basicConfig(level=logging.INFO)
    return create_app()
