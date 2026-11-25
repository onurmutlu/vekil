import time

from app.assistant import conversation, parse
from app.config import SUBSCRIPTION_PERIOD
from tests.conftest import (ADMIN, CONN, CUSTOMER, OWNER, OWNER_CHAT, connection, customer_msg, hook, init_data,
                            owner_msg, setup_ready)


def business_replies(api):
    return [p for p in api.of("sendMessage") if p.get("business_connection_id")]


def owner_notes(api):
    return [p for p in api.of("sendMessage") if p.get("chat_id") == OWNER_CHAT and not p.get("business_connection_id")]


# ------------------------------------------------------------------ connection lifecycle
def test_connection_welcomes_owner_and_stays_silent_until_switched_on(client, api, llm):
    hook(client, connection())
    (welcome,) = owner_notes(api)
    assert "bağlandı" in welcome["text"] and welcome["reply_markup"]["inline_keyboard"][0][0]["web_app"]
    hook(client, customer_msg())
    assert business_replies(api) == [] and llm.prompts == []


def test_missing_reply_right_is_explained(client, api):
    hook(client, connection(can_reply=False))
    assert "izni" in owner_notes(api)[0]["text"]


def test_assistant_cannot_be_switched_on_without_profile(client):
    hook(client, connection())
    r = client.post("/api/active", json={"active": True}, headers=init_data())
    assert r.status_code == 400


def test_disabled_connection_stops_replies(client, api):
    setup_ready(client)
    hook(client, connection(enabled=False))
    hook(client, customer_msg())
    assert business_replies(api) == []


# ------------------------------------------------------------------ replying
def test_customer_gets_ai_reply_through_business_connection(client, api, llm):
    setup_ready(client)
    llm.say("Doğum günü pastamız 1200 TL.")
    hook(client, customer_msg("Pasta ne kadar?"))
    (reply,) = business_replies(api)
    assert reply == {"business_connection_id": CONN, "chat_id": CUSTOMER, "text": "Doğum günü pastamız 1200 TL."}
    system, messages = llm.prompts[0]
    assert "1200 TL" in system and "UYDURMA" in system
    assert messages == [{"role": "user", "content": "Pasta ne kadar?"}]
    assert api.of("sendChatAction")[0]["business_connection_id"] == CONN


def test_conversation_history_is_kept(client, llm):
    setup_ready(client)
    hook(client, customer_msg("Merhaba"))
    hook(client, customer_msg("Pasta var mı?"))
    assert llm.prompts[-1][1] == [{"role": "user", "content": "Merhaba"},
                                  {"role": "assistant", "content": "Tamam."},
                                  {"role": "user", "content": "Pasta var mı?"}]


def test_duplicate_update_does_not_answer_twice(client, api):
    setup_ready(client)
    update = customer_msg(message_id=4242)
    hook(client, update)
    hook(client, update)
    assert len(business_replies(api)) == 1


def test_failed_send_is_retried_by_telegram(client, api):
    setup_ready(client)
    update = customer_msg(message_id=5151)
    api.fail["sendMessage"] = 1
    assert hook(client, update).status_code == 500
    assert hook(client, update).status_code == 200
    assert len(business_replies(api)) == 2  # first attempt failed, second delivered
    history = client.service.store.history(OWNER, CUSTOMER, 10)
    assert [h["role"] for h in history] == ["customer", "assistant"]


def test_old_messages_media_and_bots_are_ignored(client, api):
    setup_ready(client)
    hook(client, customer_msg(date=time.time() - 3600))
    media = customer_msg()
    media["business_message"].pop("text")
    media["business_message"]["photo"] = [{"file_id": "x"}]
    hook(client, media)
    bot = customer_msg()
    bot["business_message"]["from"]["is_bot"] = True
    hook(client, bot)
    assert business_replies(api) == []


def test_unknown_connection_is_ignored(client, api):
    setup_ready(client)
    hook(client, customer_msg(conn="someone-else"))
    assert business_replies(api) == []


# ------------------------------------------------------------------ owner takes over
def test_owner_typing_pauses_the_assistant_in_that_chat(client, api, llm):
    setup_ready(client)
    hook(client, owner_msg("Selam, ben Ayşe"))
    hook(client, customer_msg("Teşekkürler"))
    assert business_replies(api) == []
    # other chats keep working
    hook(client, customer_msg("Merhaba", sender=CUSTOMER + 1))
    assert len(business_replies(api)) == 1


def test_bot_echo_does_not_pause(client, api):
    setup_ready(client)
    hook(client, owner_msg("Tamam.", by_bot=True))
    hook(client, customer_msg())
    assert len(business_replies(api)) == 1


def test_owner_lines_are_marked_in_the_prompt():
    turns = conversation([{"role": "customer", "text": "a"}, {"role": "owner", "text": "b"},
                          {"role": "assistant", "text": "c"}, {"role": "customer", "text": "d"}])
    assert turns == [{"role": "user", "content": "a"},
                     {"role": "assistant", "content": "Sahibi (elle yazdı): b\nc"},
                     {"role": "user", "content": "d"}]
    assert conversation([{"role": "assistant", "text": "x"}]) == []


# ------------------------------------------------------------------ hand-off
def test_handoff_notifies_owner_and_silences_chat_until_resumed(client, api, llm):
    setup_ready(client)
    llm.say("Sizi hemen yetkiliye aktarıyorum.", handoff=True, reason="Müşteri şikayetçi")
    hook(client, customer_msg("Siparişim bozuk geldi!"))
    note = owner_notes(api)[-1]
    assert "Müşteri şikayetçi" in note["text"] and "@mehmet" in note["text"]
    hook(client, customer_msg("Cevap verin"))
    assert len(business_replies(api)) == 1
    chats = client.get("/api/chats", headers=init_data()).json()
    assert chats[0]["status"] == "handoff"
    client.post(f"/api/chats/{CUSTOMER}/resume", headers=init_data())
    hook(client, customer_msg("Tekrar merhaba"))
    assert len(business_replies(api)) == 2


def test_model_failure_hands_off_without_sending_garbage(client, api, llm):
    setup_ready(client)
    llm.error = True
    hook(client, customer_msg())
    assert business_replies(api) == []
    assert "görüşmek istiyor" in owner_notes(api)[-1]["text"]


def test_parse_is_strict_and_safe():
    assert parse('```json\n{"reply":"Selam","handoff":false,"reason":""}\n```').reply == "Selam"
    bad = parse("Sure! Here is your answer")
    assert bad.handoff and bad.reply
    assert parse('{"reply":"","handoff":true,"reason":"x"}').handoff


# ------------------------------------------------------------------ quotas and limits
def test_trial_quota_stops_replies_and_warns_once(client, api):
    setup_ready(client)  # trial_replies=3
    for i in range(5):
        hook(client, customer_msg(f"soru {i}", sender=CUSTOMER + i))
    assert len(business_replies(api)) == 3
    warnings = [n for n in owner_notes(api) if "hakkın doldu" in n["text"]]
    assert len(warnings) == 1


def test_per_chat_hourly_limit(client, api, store):
    from tests.conftest import make_settings
    client.service.settings = make_settings(max_replies_per_chat_hour=2, trial_replies=50)
    setup_ready(client)
    for i in range(4):
        hook(client, customer_msg(f"m{i}"))
    assert len(business_replies(api)) == 2


# ------------------------------------------------------------------ dashboard
def test_dashboard_requires_telegram_session(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"X-Telegram-Init-Data": "auth_date=1&hash=00"}).status_code == 401


def test_dashboard_view_and_profile(client):
    hook(client, connection())
    view = client.get("/api/me", headers=init_data()).json()
    assert view["connected"] and view["can_reply"] and not view["active"]
    assert view["quota"] == {"plan": "trial", "plan_until": None, "left": 3, "limit": 3}
    view = client.put("/api/profile", json={"business_name": "X", "about": "", "knowledge": "k", "tone": "",
                                            "handoff_note": "", "pause_minutes": 5000}, headers=init_data())
    assert view.status_code == 422  # pause_minutes out of range


def test_dashboard_works_before_connecting(client):
    view = client.get("/api/me", headers=init_data(OWNER + 1)).json()
    assert view["connected"] is False


def test_playground_uses_profile_and_daily_limit(client, llm):
    from tests.conftest import make_settings
    setup_ready(client)
    llm.say("Pastamız 1200 TL.")
    r = client.post("/api/playground", json={"messages": [{"from": "customer", "text": "Fiyat?"}]}, headers=init_data())
    assert r.json() == {"reply": "Pastamız 1200 TL.", "handoff": False, "reason": ""}
    assert "Ayşe Pasta" in llm.prompts[-1][0]
    client.service.settings = make_settings(playground_daily=1)
    r = client.post("/api/playground", json={"messages": [{"from": "customer", "text": "?"}]}, headers=init_data())
    assert r.status_code == 429


def test_chats_are_private_per_owner(client):
    setup_ready(client)
    hook(client, customer_msg())
    assert client.get("/api/chats", headers=init_data(OWNER + 7)).json() == []


# ------------------------------------------------------------------ billing
def plan_payment(order_id, charge="ch-1", amount=750, expires=None, sender=OWNER):
    return {"update_id": 9000, "message": {"message_id": 1, "chat": {"id": sender, "type": "private"},
            "from": {"id": sender}, "successful_payment": {
                "currency": "XTR", "total_amount": amount, "invoice_payload": order_id,
                "telegram_payment_charge_id": charge, "is_recurring": True, "is_first_recurring": True,
                "subscription_expiration_date": int(expires or time.time() + SUBSCRIPTION_PERIOD)}}}


def buy_plan(client):
    link = client.post("/api/billing/invoice", headers=init_data()).json()["invoice_link"]
    return link.split("$inv-")[1]


def test_plan_invoice_is_a_stars_subscription(client, api):
    hook(client, connection())
    buy_plan(client)
    (inv,) = api.of("createInvoiceLink")
    assert inv["currency"] == "XTR" and inv["subscription_period"] == SUBSCRIPTION_PERIOD
    assert inv["prices"][0]["amount"] == 750


def test_pre_checkout_validation(client, api):
    hook(client, connection())
    order_id = buy_plan(client)
    q = lambda **kw: {"update_id": 77, "pre_checkout_query": {"id": "q", "from": {"id": OWNER}, "currency": "XTR",  # noqa: E731
                                                              "total_amount": 750, "invoice_payload": order_id, **kw}}
    hook(client, q())
    hook(client, q(total_amount=1))
    hook(client, q(**{"from": {"id": 1}}))
    assert [p["ok"] for p in api.of("answerPreCheckoutQuery")] == [True, False, False]


def test_paid_plan_resets_quota_and_renewal_extends(client, api):
    setup_ready(client)
    for i in range(3):
        hook(client, customer_msg(f"t{i}", sender=CUSTOMER + 10 + i))
    order_id = buy_plan(client)
    hook(client, plan_payment(order_id))
    view = client.get("/api/me", headers=init_data()).json()
    assert view["quota"]["plan"] == "paid" and view["quota"]["left"] == 5
    hook(client, customer_msg("plan sonrası", sender=CUSTOMER + 50))
    assert client.get("/api/me", headers=init_data()).json()["quota"]["left"] == 4
    # Telegram renews with the same payload and a new charge
    hook(client, plan_payment(order_id, charge="ch-2", expires=time.time() + 2 * SUBSCRIPTION_PERIOD))
    assert client.get("/api/me", headers=init_data()).json()["quota"]["left"] == 5
    # a second purchase while active is refused
    assert client.post("/api/billing/invoice", headers=init_data()).status_code == 409


def test_unmatched_and_duplicate_payments(client, store):
    hook(client, connection())
    order_id = buy_plan(client)
    hook(client, plan_payment("nope", charge="x"))
    hook(client, plan_payment(order_id, charge="y", amount=1))
    assert {i["charge"] for i in store.open_issues()} == {"x", "y"}
    hook(client, plan_payment(order_id, charge="ok"))
    hook(client, plan_payment(order_id, charge="ok"))
    assert store.db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1


def test_refund_ends_plan(client, api, store):
    hook(client, connection())
    order_id = buy_plan(client)
    hook(client, plan_payment(order_id, charge="r1"))
    refund = {"update_id": 9100, "message": {"message_id": 2, "chat": {"id": ADMIN, "type": "private"},
                                             "from": {"id": ADMIN}, "text": "/refund r1"}}
    hook(client, refund)
    assert api.of("refundStarPayment") == [{"user_id": OWNER, "telegram_payment_charge_id": "r1"}]
    assert client.get("/api/me", headers=init_data()).json()["quota"]["plan"] == "trial"


def test_refund_command_is_admin_only(client, api):
    hook(client, connection())
    order_id = buy_plan(client)
    hook(client, plan_payment(order_id, charge="r2"))
    hook(client, {"update_id": 9200, "message": {"message_id": 3, "chat": {"id": OWNER, "type": "private"},
                                                 "from": {"id": OWNER}, "text": "/refund r2"}})
    assert api.of("refundStarPayment") == []


# ------------------------------------------------------------------ webhook and commands
def test_webhook_secret(client):
    assert client.post("/telegram/webhook", json={}).status_code == 403


def test_start_and_required_commands(client, api):
    for i, cmd in enumerate(("/start", "/paysupport", "/terms")):
        hook(client, {"update_id": 9300 + i, "message": {"message_id": i, "chat": {"id": 42, "type": "private"},
                                                        "from": {"id": 42}, "text": cmd}})
    texts = [p["text"] for p in api.of("sendMessage")]
    assert "Premium" in texts[0] and texts[1] == "destek@vekil.app" and texts[2] == "Koşullar"
