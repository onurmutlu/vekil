# SoruPilot: Trendyol AI Soru Asistanı

Trendyol satıcılarının müşteri sorularını **Telegram Bot + Claude AI** ile otomatik cevaplandıran SaaS.

## Mimari

```
Satıcı (Trendyol Seller)
    ↓
  Telegram Bot (@SoruPilotBot)
    ↓
  FastAPI (SoruPilot Service)
    ├─ Trendyol Store API (ürün veri)
    ├─ Claude LLM (AI asistan)
    └─ SQLite (mesaj history, config)
    ↓
  Seller Dashboard (/app)
    ├─ Store Settings
    ├─ Questions Log
    ├─ Usage Stats
    └─ Plan Management
```

## Teknik Stack

| Bileşen | Teknoloji |
|---------|-----------|
| Backend | FastAPI + Python |
| LLM | Anthropic Claude API |
| Bot | Telegram Bot API |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Panel | HTML5 + Vanilla JS |
| Deploy | Docker + Vercel/Cloud Run |
| Auth | Telegram Login Widget + Trendyol OAuth |

## MVP Roadmap

### Phase 1: Bot + Basic Panel ✏️
- [ ] Telegram bot setup (BotFather)
- [ ] Seller authentication (Telegram Login Widget)
- [ ] Store settings panel (/app)
- [ ] AI response engine (Claude)
- [ ] Message logging
- [ ] Deploy to production

### Phase 2: Trendyol Integration
- [ ] Trendyol Seller API client
- [ ] Product catalog syncing
- [ ] Auto-populate knowledge base
- [ ] Store metrics dashboard

### Phase 3: Monetization
- [ ] Usage tracking (message count)
- [ ] Pricing plans (Free / Pro)
- [ ] Payment system (Telegram Stars or TL)
- [ ] Subscription management

### Phase 4: Polish
- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] AI quality improvements
- [ ] Scaling to PostgreSQL

## Setup

### 1. Create Telegram Bot
```bash
# BotFather (@BotFather) üzerinde:
/newbot
# → SoruPilot Bot (@SoruPilotBot)
# → Bot Settings → Business Mode → Turn on
```

### 2. Environment Setup
```bash
cp .env.example .env
```

**`.env` dosyası:**
```
# Telegram
BOT_TOKEN=<BotFather'dan aldığın token>
WEBHOOK_SECRET=<random string>
BOT_USERNAME=SoruPilotBot
WEBAPP_URL=https://sorupilot.vercel.app

# LLM
LLM_PROVIDER=anthropic
LLM_API_KEY=<Anthropic API key>

# Trendyol (optional for now)
TRENDYOL_CLIENT_ID=<future>
TRENDYOL_CLIENT_SECRET=<future>
TRENDYOL_API_KEY=<future>

# Database
DATABASE_URL=sqlite:///./sorupilot.db

# Web
SALES_ENABLED=false
```

### 3. Install & Run
```bash
# Local development
pip install -r requirements.txt
python -m app.cli setup
python -m app.cli poll  # Webhook'lar olmadan poll mode'da

# Or with Docker
docker compose up -d --build
```

### 4. Test
```bash
# Telegram'da bot'u aç: @SoruPilotBot
# "Merhaba" yaz → AI asistan cevap verir

# Panel: http://localhost:8000/app
# Telegram Login Widget ile gir
```

## Dosya Yapısı

```
sorupilot/ (vekil repo branch'ı)
├── app/
│   ├── trendyol.py          # Trendyol API client
│   ├── assistant_sorupilot.py # Claude prompt (Trendyol-spesifik)
│   ├── service.py           # Business logic
│   ├── telegram.py          # Telegram Bot handler
│   ├── store.py             # SQLite schema
│   ├── main.py              # FastAPI app
│   ├── config.py
│   ├── llm.py
│   └── ...
├── webapp/
│   ├── index.html           # Seller dashboard
│   └── styles.css
├── deploy/
│   └── Dockerfile
├── tests/
│   └── test_sorupilot.py
├── requirements.txt
├── README_SORUPILOT.md      # (this file)
└── .env.example
```

## Development

### Add a Feature
```bash
git checkout sorupilot
# edit files
git add .
git commit -m "feature: xyz"
```

### Run Tests
```bash
pip install -r requirements-dev.txt
pytest tests/test_sorupilot.py -v
```

### Deploy
```bash
# Vercel (web panel)
vercel deploy

# Backend (Cloud Run / Railway / Replit)
docker push <registry>/<image>:latest
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Check BOT_TOKEN, webhook secret |
| Claude API error | Verify LLM_API_KEY |
| Panel login fails | Check TELEGRAM_LOGIN_WIDGET config |
| Trendyol integration not working | Implement OAuth first (Phase 2) |

## Support

- 📧 Issues: GitHub issues
- 💬 Contact: @SiyahKare (Telegram)
- 📚 Docs: [Trendyol Seller API](https://developer.trendyol.com) (future)

---

**Version**: 0.1.0 (MVP)  
**Status**: 🔨 In Development  
**Last Updated**: Nov 28, 2026
