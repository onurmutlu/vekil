"""Vekil core: Telegram Business updates, AI replies, hand-off, quotas and Stars billing."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Awaitable, Callable

from .assistant import Decision, conversation, parse, system_prompt
from .config import SUBSCRIPTION_PERIOD, Settings
from .store import Store

log = logging.getLogger("vekil")
Api = Callable[..., Awaitable]
LLM = Callable[[str, list], Awaitable[str]]
MAX_UPDATE_FAILURES = 3


class ServiceError(Exception):
    """An error whose message is safe to show to the owner."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _name(user: dict) -> str:
    return " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x).strip()


class Vekil:
    def __init__(self, api: Api, llm: LLM, settings: Settings, store: Store):
        self.api, self.llm, self.settings, self.store = api, llm, settings, store

    # ------------------------------------------------------------------ quota
    def allowance(self, account, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        plan_until = self.store.plan_until(account["owner_id"])
        if plan_until > now:
            left = self.settings.plan_replies - account["period_used"]
            return {"plan": "paid", "plan_until": plan_until, "left": max(0, left),
                    "limit": self.settings.plan_replies}
        left = self.settings.trial_replies - account["trial_used"]
        return {"plan": "trial", "plan_until": None, "left": max(0, left), "limit": self.settings.trial_replies}

    # ------------------------------------------------------------------ updates
    async def handle_update(self, update: dict) -> None:
        if "business_connection" in update:
            await self._connection(update["business_connection"])
        elif "business_message" in update:
            await self._business_message(update["business_message"])
        elif "pre_checkout_query" in update:
            await self._pre_checkout(update["pre_checkout_query"])
        elif "message" in update:
            await self._bot_message(update["message"])
        # edited_business_message / deleted_business_messages: nothing to do in the MVP

    async def _connection(self, conn: dict) -> None:
        user = conn["user"]
        rights = conn.get("rights") or {}
        can_reply = bool(rights.get("can_reply", conn.get("can_reply", False)))
        enabled = bool(conn.get("is_enabled"))
        before = self.store.account(user["id"])
        self.store.set_connection(user["id"], _name(user), conn["id"], conn["user_chat_id"], enabled, can_reply)
        if not enabled:
            await self._notify(conn["user_chat_id"], "Vekil bağlantısı kapatıldı. Asistan artık mesajlarına cevap vermiyor.")
            return
        if not can_reply:
            text = ("Vekil bağlandı ama mesajlara cevap verme izni kapalı. Telegram > Ayarlar > Telegram Business > "
                    "Sohbet botları bölümünden 'Mesajlara cevap ver' iznini aç.")
        elif before and before["connected"]:
            return  # settings changed, still fine
        else:
            text = ("✅ Vekil hesabına bağlandı. Şimdi panelden işletme bilgilerini ve fiyatlarını gir, "
                    "deneme alanında test et ve asistanı aç. Sen açana kadar hiçbir müşteriye cevap vermez.")
        await self._notify(conn["user_chat_id"], text, dashboard=True)

    async def _business_message(self, message: dict) -> None:
        account = self.store.account_by_connection(message.get("business_connection_id", ""))
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if not account or chat.get("type") != "private":
            return
        owner_id, chat_id = account["owner_id"], chat["id"]
        text = (message.get("text") or message.get("caption") or "").strip()

        if sender.get("id") == owner_id:
            if message.get("sender_business_bot"):
                return  # our own reply, echoed back
            # The owner typed in this chat: step back for a while.
            if text:
                self.store.add_message(owner_id, chat_id, "owner", text)
            self.store.pause_chat(owner_id, chat_id, time.time() + account["pause_minutes"] * 60)
            return
        if sender.get("is_bot") or not self.store.first_time(owner_id, chat_id, message.get("message_id", 0)):
            return

        self.store.touch_chat(owner_id, chat_id, _name(sender), sender.get("username") or "", text or "(medya)")
        if not text:
            return  # photos, voice, stickers: left to the owner in the MVP
        self.store.add_message(owner_id, chat_id, "customer", text)

        state = self.store.chat(owner_id, chat_id)
        if not (account["active"] and account["connected"] and account["can_reply"]):
            return
        if state["status"] == "handoff" or state["paused_until"] > time.time():
            return
        if time.time() - message.get("date", time.time()) > self.settings.max_message_age:
            return
        if self.store.replies_last_hour(owner_id, chat_id) >= self.settings.max_replies_per_chat_hour:
            log.warning("Saatlik yanıt sınırı: owner=%s chat=%s", owner_id, chat_id)
            return
        quota = self.allowance(account)
        if quota["left"] <= 0:
            await self._quota_notice(account)
            return

        conn_id = account["connection_id"]
        try:
            await self.api("sendChatAction", business_connection_id=conn_id, chat_id=chat_id, action="typing")
        except Exception:  # noqa: BLE001 - typing is cosmetic
            pass
        decision = await self.decide(account, self.store.history(owner_id, chat_id, self.settings.history_messages))
        if decision.reply:
            try:
                await self.api("sendMessage", business_connection_id=conn_id, chat_id=chat_id, text=decision.reply)
            except Exception:
                # Nothing reached the customer: let Telegram's retry of this update try again.
                self.store.forget(owner_id, chat_id, message.get("message_id", 0))
                raise
            self.store.add_message(owner_id, chat_id, "assistant", decision.reply)
            self.store.count_reply(owner_id, chat_id, paid=quota["plan"] == "paid")
        if decision.handoff:
            self.store.set_chat_status(owner_id, chat_id, "handoff", decision.reason)
            who = _name(sender) or "Bir müşteri"
            handle = f" (@{sender['username']})" if sender.get("username") else ""
            await self._notify(account["user_chat_id"],
                               f"🙋 {who}{handle} seninle görüşmek istiyor.\nNeden: {decision.reason or 'belirtilmedi'}\n"
                               f"Son mesaj: {text[:300]}\n\nAsistan bu sohbette sen panelden devam ettirene kadar susacak.",
                               dashboard=True)

    async def decide(self, account, history: list[dict]) -> Decision:
        try:
            raw = await self.llm(system_prompt(account), conversation(history))
        except Exception as exc:  # noqa: BLE001
            log.error("Model hatası: %s", type(exc).__name__)
            return Decision("", True, "Asistan şu an cevap üretemedi; müşteri cevap bekliyor")
        return parse(raw)

    async def _quota_notice(self, account) -> None:
        if time.time() - account["quota_notice"] < 86400:
            return
        self.store.set_quota_notice(account["owner_id"], time.time())
        await self._notify(account["user_chat_id"],
                           "⚠️ AI yanıt hakkın doldu. Müşteri mesajları cevapsız kalmasın diye panelden planını yenile.",
                           dashboard=True)

    async def _notify(self, chat_id: int | None, text: str, dashboard: bool = False) -> None:
        if not chat_id:
            return
        extra = {}
        if dashboard:
            extra["reply_markup"] = {"inline_keyboard": [[{"text": "⚙️ Paneli aç", "web_app": {"url": self.settings.webapp_url}}]]}
        try:
            await self.api("sendMessage", chat_id=chat_id, text=text, **extra)
        except Exception as exc:  # noqa: BLE001 - owner may have blocked the bot
            log.warning("Sahibe bildirim gönderilemedi: %s", type(exc).__name__)

    # ------------------------------------------------------------------ private chat with our bot
    async def _bot_message(self, message: dict) -> None:
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if chat.get("type") != "private" or sender.get("is_bot"):
            return
        if message.get("successful_payment"):
            await self._successful_payment(sender["id"], message["successful_payment"])
            return
        if message.get("refunded_payment"):
            self.store.mark_refunded(message["refunded_payment"]["telegram_payment_charge_id"])
            return
        command, _, arg = (message.get("text") or "").strip().partition(" ")
        command = command.split("@")[0].lower()
        if command == "/paysupport":
            reply = self.settings.support_text or "Destek bilgisi henüz tanımlanmadı."
        elif command == "/terms":
            reply = self.settings.terms_text or "Koşullar henüz tanımlanmadı."
        elif command == "/refund" and sender["id"] in self.settings.admin_ids:
            reply = await self._admin_refund(arg.strip())
        else:
            await self._notify(chat["id"], (
                f"{self.settings.product_name}: Telegram'da müşterilerine senin yerine cevap veren AI asistan.\n\n"
                "1) Panelden işletme bilgilerini gir\n2) Ayarlar > Telegram Business > Sohbet botları'na bu botu ekle\n"
                "3) Deneme alanında test et, asistanı aç\n\nTelegram Business özellikleri Telegram Premium gerektirir.\n"
                "Destek: /paysupport · Koşullar: /terms"), dashboard=True)
            return
        await self.api("sendMessage", chat_id=chat["id"], text=reply)

    # ------------------------------------------------------------------ dashboard actions
    def view(self, owner_id: int) -> dict:
        account = self.store.account(owner_id)
        if not account:
            raise ServiceError("Hesap bulunamadı.", 404)
        quota = self.allowance(account)
        return {
            "connected": bool(account["connected"]), "can_reply": bool(account["can_reply"]),
            "active": bool(account["active"]),
            "profile": {k: account[k] for k in ("business_name", "about", "knowledge", "tone", "handoff_note",
                                                 "pause_minutes")},
            "quota": quota,
            "plan": {"stars": self.settings.plan_stars, "replies": self.settings.plan_replies,
                     "sales_enabled": self.settings.sales_enabled},
            "support": self.settings.support_text, "terms": self.settings.terms_text,
            "bot_username": self.settings.bot_username, "product_name": self.settings.product_name,
        }

    def set_active(self, owner_id: int, active: bool) -> None:
        account = self.store.account(owner_id)
        if active and not (account["business_name"] and account["knowledge"]):
            raise ServiceError("Önce işletme adını ve bilgi bankasını doldur.")
        self.store.set_active(owner_id, active)

    def chats(self, owner_id: int) -> list[dict]:
        now = time.time()
        return [{"chat_id": c["chat_id"], "name": c["customer_name"], "username": c["username"],
                 "status": c["status"], "reason": c["handoff_reason"], "last_text": c["last_text"],
                 "last_at": c["last_at"], "paused": c["paused_until"] > now} for c in self.store.chats(owner_id)]

    def resume(self, owner_id: int, chat_id: int) -> None:
        if not self.store.chat(owner_id, chat_id):
            raise ServiceError("Sohbet bulunamadı.", 404)
        self.store.set_chat_status(owner_id, chat_id, "ai")
        self.store.pause_chat(owner_id, chat_id, 0)

    async def playground(self, owner_id: int, messages: list[dict]) -> dict:
        if self.store.playground_today(owner_id) >= self.settings.playground_daily:
            raise ServiceError("Bugünkü deneme hakkın bitti, yarın tekrar dene.", 429)
        account = self.store.account(owner_id)
        history = [{"role": "customer" if m.get("from") == "customer" else "assistant", "text": str(m.get("text", ""))[:1000]}
                   for m in messages[-12:]]
        if not history or history[-1]["role"] != "customer":
            raise ServiceError("Son mesaj müşteriden olmalı.")
        self.store.count_playground(owner_id)
        decision = await self.decide(account, history)
        return {"reply": decision.reply, "handoff": decision.handoff, "reason": decision.reason}

    # ------------------------------------------------------------------ billing (Telegram Stars)
    async def plan_invoice(self, owner_id: int) -> dict:
        if not self.settings.sales_enabled:
            raise ServiceError("Abonelik satışı henüz açık değil.", 403)
        if self.store.plan_until(owner_id) > time.time():
            raise ServiceError("Planın zaten aktif; Telegram her 30 günde otomatik yeniler.", 409)
        order_id = uuid.uuid4().hex
        self.store.create_order(order_id, owner_id, self.settings.plan_stars)
        link = await self.api(
            "createInvoiceLink", title=f"{self.settings.product_name} Pro"[:32],
            description=f"Aylık {self.settings.plan_replies} AI yanıtı. 30 günde bir yenilenir, Telegram'dan iptal edilebilir.",
            payload=order_id, currency="XTR", subscription_period=SUBSCRIPTION_PERIOD,
            prices=[{"label": "Aylık plan", "amount": self.settings.plan_stars}])
        return {"invoice_link": link}

    async def _pre_checkout(self, query: dict) -> None:
        order = self.store.order(query.get("invoice_payload", ""))
        ok = bool(self.settings.sales_enabled and order and order["owner_id"] == query["from"]["id"]
                  and query.get("currency") == "XTR" and query.get("total_amount") == order["stars"]
                  and time.time() - order["created"] <= 3600)
        extra = {} if ok else {"error_message": "Ödeme bağlantısının süresi doldu. Panelden yeniden dene."}
        await self.api("answerPreCheckoutQuery", pre_checkout_query_id=query["id"], ok=ok, **extra)

    async def _successful_payment(self, owner_id: int, payment: dict) -> None:
        charge = payment["telegram_payment_charge_id"]
        if self.store.payment(charge):
            return
        order = self.store.order(payment.get("invoice_payload", ""))
        expires = payment.get("subscription_expiration_date")
        if (not order or order["owner_id"] != owner_id or payment.get("currency") != "XTR"
                or payment.get("total_amount") != order["stars"] or not expires):
            self.store.record_issue(charge, owner_id, payment.get("total_amount"), payment.get("invoice_payload"),
                                    "no_matching_order")
            log.error("Ödeme eşleşmedi, operatör gerekli: charge=%s", charge)
            return
        self.store.ensure_account(owner_id)
        self.store.add_payment(charge, owner_id, order["stars"], expires)
        await self._notify(owner_id, f"⭐ Planın aktif. Bu dönem {self.settings.plan_replies} AI yanıtın var.", dashboard=True)

    async def _admin_refund(self, charge: str) -> str:
        if not charge:
            return "Kullanım: /refund <telegram_payment_charge_id>"
        owner = self.store.payment(charge) or self.store.db.execute(
            "SELECT owner_id FROM payment_issues WHERE charge=?", (charge,)).fetchone()
        if not owner:
            return "Bu ödeme kimliği için kayıt yok."
        if self.store.is_refunded(charge):
            return "Bu ödeme zaten iade edilmiş."
        await self.api("refundStarPayment", user_id=owner["owner_id"], telegram_payment_charge_id=charge)
        self.store.mark_refunded(charge)
        return "İade edildi."


async def process_update(service: Vekil, update: dict, failures: dict[int, int]) -> None:
    """Retry a failing update a few times (webhook answers 500), then skip it,
    keeping any payment inside it for the operator."""
    update_id = update.get("update_id", -1)
    try:
        await service.handle_update(update)
    except Exception as exc:
        failures[update_id] = failures.get(update_id, 0) + 1
        if failures[update_id] < MAX_UPDATE_FAILURES:
            raise
        failures.pop(update_id, None)
        message = update.get("message") or {}
        payment = message.get("successful_payment")
        if payment:
            service.store.record_issue(payment.get("telegram_payment_charge_id"), message.get("from", {}).get("id"),
                                       payment.get("total_amount"), payment.get("invoice_payload"),
                                       f"update_failed:{type(exc).__name__}")
        log.error("Güncelleme %s atlandı (%s)", update_id, type(exc).__name__)
    else:
        failures.pop(update_id, None)
