# Vekil: Telegram Business AI asistanı

İşletmenin **kendi Telegram hesabına** bağlanıp müşterilere işletme adına, işletmenin verdiği bilgilerle cevap veren
AI asistan. İşletme sahibi her şeyi bir Mini App panelinden yönetir ve Telegram Stars ile abone olur.

*English summary at the end.*

## Nasıl çalışır

1. İşletme sahibi botu açar, **Panel**'den işletme adı, açıklama, **bilgi bankası** (fiyatlar, saatler, kurallar),
   üslup ve devretme kurallarını girer.
2. Telegram'da *Ayarlar → Telegram Business → Sohbet botları* bölümünden botu ekler ve
   *Mesajlara cevap ver* iznini verir. (Telegram Business, Telegram Premium gerektirir.)
3. Paneldeki **Dene** sekmesinde müşteri gibi yazıp asistanı test eder, sonra anahtarla açar.
4. Asistan müşteri mesajlarına sahibinin hesabından cevap verir:
   - **Sadece bilgi bankasındaki bilgilerle** cevap verir. Bilgi yoksa uydurmaz, "kontrol edip döneceğim" der ve devreder.
   - Şikayet, insan isteği, pazarlık, özel sipariş, iade, ödeme sorunu gibi durumlarda **sahibine devreder**:
     sahibine bildirim gider, o sohbette asistan susar, panelden "Asistan devam etsin" denene kadar cevap vermez.
   - **Sahibi bir sohbete kendisi yazarsa** asistan o sohbette belirlenen süre (varsayılan 30 dk) boyunca susar.
   - "Bot musun?" diye doğrudan sorulursa dürüstçe AI asistan olduğunu söyler.
5. Deneme: hesap başına 50 ücretsiz AI yanıtı. Sonrası **Pro**: aylık Stars aboneliği (varsayılan 750 ⭐ / 2.000 yanıt).

## Güvenlik ve sağlamlık

- Panel isteklerinin hepsi Telegram `initData` imzasıyla doğrulanır; her işletme sadece kendi verisini görür.
- Webhook `X-Telegram-Bot-Api-Secret-Token` ile korunur.
- Aynı müşteri mesajına iki kez cevap verilmez (webhook tekrarları). Gönderim başarısız olursa Telegram'ın tekrarıyla yeniden denenir.
- 10 dakikadan eski birikmiş mesajlara, botlara ve medya mesajlarına cevap verilmez.
  Sohbet başına saatte en fazla 30 yanıt sınırı vardır; bu, başka botlarla döngüye girmeyi engeller.
- Model hata verirse ya da geçersiz çıktı üretirse müşteriye hiçbir şey gönderilmez, sahibine devredilir.
- Ödemeler: `pre_checkout` sıkı doğrulanır, `charge_id` tekildir, eşleşmeyen ödemeler `payment_issues` tablosuna düşer.
  Admin `/refund <charge_id>` ile iade eder. Telegram'ın yaptığı iadeler de planı kapatır.

## Yapı

```
app/
  service.py    iş mantığı: bağlantı, müşteri mesajı, devretme, kota, Stars abonelik
  assistant.py  sistem talimatı, sohbet geçmişi dönüşümü, model çıktısının güvenli ayrıştırılması
  llm.py        Anthropic / OpenAI / echo (anahtarsız geliştirme)
  store.py      SQLite tabloları
  main.py       FastAPI: panel, /api/*, /telegram/webhook
  cli.py        setup / poll / issues
  initdata.py, telegram.py, config.py
webapp/         Panel (derleme gerektirmeyen HTML/CSS/JS): Ayarlar · Dene · Sohbetler · Plan
tests/          31 test
```

## Kurulum

1. @BotFather: bot oluştur → *Bot Settings → Business Mode → Turn on*.
2. `cp .env.example .env` ve doldur (`BOT_TOKEN`, `WEBHOOK_SECRET`, `WEBAPP_URL`, `LLM_API_KEY`).
3. `docker compose up -d --build` (ya da `pip install -r requirements.txt && uvicorn app.main:app --factory`).
4. HTTPS: sunucunun önüne Caddy/Nginx koy ya da geliştirmede `cloudflared tunnel --url http://localhost:8000`.
5. `python -m app.cli setup`: webhook, *Panel* menü butonu ve komutlar ayarlanır. Business Mode kapalıysa uyarır.
6. Önce `LLM_PROVIDER=echo` ve `SALES_ENABLED=false` ile dene. Sonra gerçek modelle kendi Business hesabını bağla,
   başka bir hesaptan mesaj atıp test et. 1 Star'lık geçici bir planla ödeme/iade akışını dene, sonra satışı aç.

Webhook olmadan yerelde: `python -m app.cli poll`.

## Bilinen sınırlar (MVP)

- Fotoğraf, ses ve dosya mesajları sahibine bırakılır (asistan cevap vermez).
- Bilgi bankası düz metindir (8.000 karakter). Uzun kataloglar için ileride arama tabanlı bilgi bankası gerekir.
- SQLite tek süreç içindir. Çok sayıda işletmede PostgreSQL'e ve bir iş kuyruğuna geçilmeli (model çağrıları webhook içinde yapılıyor).
- Yanıt maliyeti seçilen modele bağlıdır. Plan fiyatını model maliyetine ve Stars kazanç kuruna göre ayarla.

## Testler

```bash
pip install -r requirements-dev.txt && pytest
```

---

## English summary

Vekil connects to a Telegram Business account (Bot API business connections) and answers customers **as the
owner**, strictly from the owner's knowledge base. It hands off to the human on complaints, human requests,
negotiations, refunds or anything unknown. It pauses in a chat when the owner types, never answers twice,
and never sends raw model output. Owners configure everything in a Mini App dashboard (profile, playground,
conversations, plan) and subscribe with Telegram Stars. FastAPI + SQLite, Anthropic/OpenAI providers, 31 tests.
