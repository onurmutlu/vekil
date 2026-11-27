# SoruPilot: 5 Dakika Quick Start 🚀

## 1️⃣ Bot Oluştur (2 dk)

BotFather'a git: https://t.me/BotFather

```
/newbot
Adı: SoruPilot
Username: SoruPilotBot
```

Aldığın token'ı sakla → `.env` dosyasına koy

BotFather'da devam:
```
/mybots → SoruPilotBot → Bot Settings → Business Mode → Turn on
```

## 2️⃣ Environment Setup (1 dk)

```bash
cp .env.example .env
```

**`.env` dosyasını aç ve doldur:**
```env
BOT_TOKEN=<BotFather'dan aldığın token>
WEBHOOK_SECRET=asdfa32f32f32f3
BOT_USERNAME=SoruPilotBot
WEBAPP_URL=http://localhost:8000  # (local) veya https://sorupilot.example.com (prod)
LLM_API_KEY=<anthropic API key>
LLM_PROVIDER=anthropic
DATABASE_URL=sqlite:///./sorupilot.db
SALES_ENABLED=false  # (başlangıçta)
```

## 3️⃣ Çalıştır (2 dk)

### Seçenek A: Local Docker (Recommended for testing)
```bash
docker compose up -d --build
# → http://localhost:8000
```

### Seçenek B: Local Development
```bash
pip install -r requirements.txt
python -m app.cli setup
python -m app.cli poll
```

### Seçenek C: Production (Cloud Run)
```bash
./deploy.sh cloudrun my-gcp-project us-central1
```

## 4️⃣ Test Et (!)

**Telegram'da:**
1. @SoruPilotBot'u aç
2. "Merhaba" yaz
3. Bot cevap verirse ✅

**Panel:**
1. http://localhost:8000/app (or prod URL)
2. "Telegram Login Widget" ile gir
3. Mağaza ayarlarını doldur
4. "Test" sekmesinde mesaj yaz

## 📋 Next Steps

- [ ] Store bilgilerini doldur (Panel > Settings)
- [ ] AI cevaplarını test et (Panel > Playground)
- [ ] Bot'u mağaza için açık hale getir (Panel > Toggle Active)
- [ ] Trendyol API entegrasyonunu yap (Phase 2)
- [ ] Production'a deploy et

---

## 🆘 Troubleshooting

| Problem | Çözüm |
|---------|-------|
| Bot doesn't reply | ✓ BOT_TOKEN doğru mu? ✓ Business Mode açık mı? |
| Panel login fails | ✓ WEBAPP_URL doğru mu? ✓ Telegram Login Widget configured? |
| "Claude API error" | ✓ LLM_API_KEY doğru mu? |
| Docker fails | ✓ Docker kurulu mu? (`docker --version`) |

---

**Ready? Let's go!** 🎯

```bash
docker compose up
```

Then open: http://localhost:8000/app
