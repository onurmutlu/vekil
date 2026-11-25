import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app import initdata
from app.config import Settings
from app.main import create_app
from app.store import Store

TOKEN = "123456:TEST"
SECRET = "w" * 40
OWNER = 500
OWNER_CHAT = 500
CUSTOMER = 700
CONN = "bc-1"
ADMIN = 999


class FakeAPI:
    def __init__(self):
        self.calls, self.fail = [], {}

    async def __call__(self, method, **payload):
        self.calls.append((method, payload))
        if self.fail.get(method):
            self.fail[method] -= 1
            raise RuntimeError(method)
        if method == "createInvoiceLink":
            return "https://t.me/$inv-" + payload["payload"]
        return True

    def of(self, method):
        return [p for m, p in self.calls if m == method]


class FakeLLM:
    """Returns queued raw outputs; records prompts."""

    def __init__(self):
        self.outputs, self.prompts = [], []
        self.error = False

    def say(self, reply="Merhaba, nasıl yardımcı olabilirim?", handoff=False, reason=""):
        self.outputs.append(json.dumps({"reply": reply, "handoff": handoff, "reason": reason}, ensure_ascii=False))

    async def __call__(self, system, messages):
        self.prompts.append((system, messages))
        if self.error:
            raise RuntimeError("model down")
        return self.outputs.pop(0) if self.outputs else json.dumps({"reply": "Tamam.", "handoff": False, "reason": ""})


def init_data(user_id=OWNER):
    fields = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": user_id, "first_name": "Ayşe"}, separators=(",", ":"))}
    fields["hash"] = initdata.sign(fields, TOKEN)
    return {"X-Telegram-Init-Data": urlencode(fields)}


def make_settings(**overrides):
    values = dict(bot_token=TOKEN, webhook_secret=SECRET, webapp_url="https://vekil.example.com",
                  support_text="destek@vekil.app", terms_text="Koşullar", llm_provider="echo",
                  sales_enabled=True, trial_replies=3, plan_stars=750, plan_replies=5,
                  admin_ids=frozenset({ADMIN}))
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def api():
    return FakeAPI()


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def client(api, llm, store):
    app = create_app(make_settings(), store, api, llm)
    with TestClient(app) as c:
        c.service = app.state.service
        yield c


def hook(client, update):
    return client.post("/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})


def connection(enabled=True, can_reply=True, conn=CONN):
    return {"update_id": 1, "business_connection": {
        "id": conn, "user": {"id": OWNER, "first_name": "Ayşe", "last_name": "Kaya"}, "user_chat_id": OWNER_CHAT,
        "date": int(time.time()), "rights": {"can_reply": can_reply}, "is_enabled": enabled}}


_mid = [100]


def customer_msg(text="Fiyat nedir?", sender=CUSTOMER, conn=CONN, date=None, message_id=None, **extra):
    _mid[0] += 1
    return {"update_id": _mid[0], "business_message": {
        "message_id": message_id or _mid[0], "business_connection_id": conn, "date": int(date or time.time()),
        "chat": {"id": sender, "type": "private"},
        "from": {"id": sender, "first_name": "Mehmet", "username": "mehmet"}, "text": text, **extra}}


def owner_msg(text="Ben bakıyorum", chat=CUSTOMER, by_bot=False):
    _mid[0] += 1
    msg = {"message_id": _mid[0], "business_connection_id": CONN, "date": int(time.time()),
           "chat": {"id": chat, "type": "private"}, "from": {"id": OWNER, "first_name": "Ayşe"}, "text": text}
    if by_bot:
        msg["sender_business_bot"] = {"id": 1, "is_bot": True, "first_name": "Vekil"}
    return {"update_id": _mid[0], "business_message": msg}


def setup_ready(client):
    """Connected, profile filled, assistant on."""
    hook(client, connection())
    client.put("/api/profile", json={"business_name": "Ayşe Pasta", "about": "Ev yapımı pasta",
                                     "knowledge": "Doğum günü pastası 1200 TL. Teslimat Kocaeli içi.",
                                     "tone": "samimi", "handoff_note": "", "pause_minutes": 30},
               headers=init_data())
    assert client.post("/api/active", json={"active": True}, headers=init_data()).status_code == 200
