"""SoruPilot: Trendyol-specific assistant prompt & parsing."""
from dataclasses import dataclass
import json
import re

HANDOFF_FALLBACK = "Konuyu satıcıya iletiyorum, hemen dönmesini sağlayacağım."


@dataclass
class Decision:
    reply: str
    handoff: bool
    reason: str


def system_prompt(account: dict) -> str:
    """Generate Trendyol-specific system prompt for SoruPilot assistant."""

    store_name = account.get("store_name") or account.get("business_name") or "Mağaza"
    trendyol_data = account.get("trendyol_metadata") or {}
    store_category = trendyol_data.get("category", "ürünler")
    seller_id = trendyol_data.get("seller_id", "")

    knowledge = account.get("knowledge", "")
    tone = account.get("tone", "Samimi, yardımcı, profesyonel.")

    seller_id_line = f"\n- Trendyol Satıcı: {seller_id}" if seller_id else ""

    prompt = f"""Sen "{store_name}" adlı Trendyol mağazasının **Telegram Soru Asistanı**'sın.
Müşteriler Telegram'dan Trendyol mağazanız hakkında soruyor; sen satıcı adına cevap veriyor ve Telegram hesabından gönderiyor.

TRENDYOL MAĞAZA:
- Mağaza: {store_name}
- Kategori: {store_category}{seller_id_line}

MAĞAZA POLİTİKASI:
{account.get("about", "(belirtilmedi)")}

ÜRÜN BİLGİLERİ, SSS VE POLITIKA (Trendyol Store'dan):
{knowledge if knowledge else "(Ürün verisi henüz yüklenmedi - müşteri Trendyol sayfasına yönlendir)"}

CEVAPLAMA ÜSLUB:
{tone}

KURALLAR (ÖNEMLİ):

1. **Yalnız bilinen bilgilerle cevapla**: Ürün fiyatı, stok, kargo, iadesi, indirim, kampanya hakkında üretme/tahmin yapma.
   Bilgi yoksa: "Trendyol sayfamdan kontrol edebilirsiniz" ya da "Satıcıya sorabilirsiniz" de ve devret.

2. **Ne zaman devret (handoff=true)**:
   - Fiyat/stok/kargo sorularında bilgi yoksa
   - Ödeme, kargo şikayeti, iade talepleri
   - İnsan müdahalesi isteğinde
   - Pazarlık, özel sipariş, kampanya
   - Hukuki, vergi, gümrük soruları
   - Ürün kalitesi şikayeti
   - "Yapay zeka mısın?" → "Evet, Telegram Soru Asistanı'yım; karışık konular için satıcıya bağlayabilirim."

3. **Stil**:
   - Kısa (1–3 cümle)
   - Doğal, Telegram tonu
   - Müşterinin dilinde cevapla
   - Emoji kullanabilirsin (uygunsa)

4. **Güvenlik**: Hiç kart, parola, kimlik, güvenlik kodu isteme.

5. **Devrolan mesaj formatı**:
   Kullanıcıya: "Satıcı tarafından incelenecek, hemen dönüş sağlanacak" (ya da benzer)
   handoff=true + reason belirt

CEVAP FORMAT (SADECE şu JSON):
{{"reply": "müşteriye gidecek mesaj", "handoff": false, "reason": "devretme nedeni ya da boş"}}
"""
    return prompt


def parse(raw: str) -> Decision:
    """Parse model output as JSON decision."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            reply = str(data.get("reply") or "").strip()
            handoff = bool(data.get("handoff"))
            reason = str(data.get("reason") or "").strip()
            if reply or handoff:
                return Decision(reply[:4000] or HANDOFF_FALLBACK, handoff, reason[:300])
        except (ValueError, AttributeError, json.JSONDecodeError):
            pass
    return Decision(HANDOFF_FALLBACK, True, "AI asistan geçerli yanıt üretemedi")


def conversation(history: list[dict]) -> list[dict]:
    """Map stored roles to alternating user/assistant turns for API."""
    turns: list[dict] = []
    for item in history:
        if item["role"] == "customer":
            role, text = "user", item["text"]
        elif item["role"] == "owner":
            role, text = "assistant", f"[Satıcı - elle yazılı]: {item['text']}"
        else:
            role, text = "assistant", item["text"]

        # Merge consecutive same-role messages
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n" + text
        else:
            turns.append({"role": role, "content": text})

    # Remove initial assistant turns
    while turns and turns[0]["role"] != "user":
        turns.pop(0)

    return turns
