# SoruPilot Production Deployment: vekil.siyahkare.com

## 🎯 Target
- **Domain:** vekil.siyahkare.com
- **Service:** SoruPilot (Telegram Bot + AI Panel)
- **Stack:** FastAPI + Claude LLM + Telegram Bot API

---

## 📋 Setup Checklist

### 1️⃣ BotFather Setup (5 min) - BARON YAPMALI
```
Telegram: @BotFather
/newbot
Adı: SoruPilot
Username: SoruPilotBot

Bot Settings:
  → Business Mode: ON
  → Copy BOT_TOKEN
  → Set Webhook Domain: vekil.siyahkare.com
```

### 2️⃣ Anthropic API Key (1 min) - BARON YAPMALI
```
https://console.anthropic.com
API Key al → LLM_API_KEY
```

### 3️⃣ Cloudflare Setup (5 min) - BARON YAPMALI
```
1. siyahkare.com'u Cloudflare'e ekle
2. DNS > Add Record:
   Type: CNAME
   Name: vekil
   Content: <VPS_IP_or_Railway_URL>
   TTL: Auto
   
3. SSL/TLS: Automatic
4. Workers (optional): Rate limiting
```

### 4️⃣ Server Setup - BARON'UN SEÇİMİ

**Option A: Railway (Recommended)**
```bash
# BARON'ın makinesinde:
npm install -g @railway/cli
railway login
railway link
./deploy.sh railway

# → vekil.siyahkare.com'u Railway'in URL'sine CNAME yap
```

**Option B: Render**
```bash
# Render.com
# Create Web Service
# Connect github.com/onurmutlu/vekil (sorupilot branch)
# Deploy
```

**Option C: Self-hosted (VPS)**
```bash
# Digital Ocean / AWS / Linode
ssh root@vps_ip

# Docker install
curl -fsSL https://get.docker.com | sh

# Clone repo
git clone https://github.com/onurmutlu/vekil.git
cd vekil
git checkout sorupilot

# .env setup
cp .env.example .env
# Edit:
BOT_TOKEN=<BotFather token>
LLM_API_KEY=<Anthropic API>
WEBHOOK_SECRET=<random>
WEBAPP_URL=https://vekil.siyahkare.com

# Run with Docker
docker compose up -d

# Certbot (auto SSL)
docker run --rm -it -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/www/certbot:/var/www/certbot \
  certbot/certbot certonly --standalone -d vekil.siyahkare.com

# Nginx reverse proxy (opsiyonel)
# Forward https://vekil.siyahkare.com → localhost:8000
```

---

## 🔧 Configuration Files

Create `.env` file:
```env
# Telegram
BOT_TOKEN=<BotFather token>
BOT_USERNAME=SoruPilotBot
WEBHOOK_SECRET=asdfa32f32f32f3
WEBAPP_URL=https://vekil.siyahkare.com

# LLM
LLM_PROVIDER=anthropic
LLM_API_KEY=<Anthropic API key>
LLM_MODEL=claude-haiku-5-5

# Database
DATABASE_URL=sqlite:///./data/sorupilot.db

# Web
SALES_ENABLED=false
TRIAL_REPLIES=50
PLAN_STARS=750
PLAN_REPLIES=2000

# Telegram Login Widget
# (BotFather'da set domain: vekil.siyahkare.com)
```

---

## 🚀 Deployment Steps

### After Server Setup:

```bash
# 1. Setup webhook
python -m app.cli setup

# 2. Test bot
# Telegram: @SoruPilotBot
# "Merhaba" yaz → AI cevap vermeli

# 3. Test panel
# https://vekil.siyahkare.com/app
# Telegram Login Widget ile gir

# 4. Configure store (Panel > Settings)
# - Mağaza adı
# - Açıklama
# - Bilgi bankası (Trendyol ürünleri)
# - Üslub
```

---

## 📡 DNS Configuration (Cloudflare)

```dns
vekil.siyahkare.com  CNAME  <deployment-url>
                            (Railway URL / VPS IP / Render URL)
```

Then wait 5-10 min for DNS to propagate.

---

## ✅ Verification Checklist

- [ ] DNS resolves: `nslookup vekil.siyahkare.com`
- [ ] SSL works: https://vekil.siyahkare.com (green lock)
- [ ] Bot responds: @SoruPilotBot on Telegram
- [ ] Panel loads: vekil.siyahkare.com/app
- [ ] Telegram Login works
- [ ] Store settings save
- [ ] AI generates responses
- [ ] Webhook registered (python -m app.cli setup)

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Bot doesn't respond" | ✓ BOT_TOKEN correct? ✓ Webhook registered? |
| "SSL error" | ✓ Wait DNS propagation ✓ Check Cloudflare SSL |
| "Panel login fails" | ✓ WEBAPP_URL=https://vekil.siyahkare.com ✓ Set domain in BotFather |
| "Database error" | ✓ Check permissions ✓ Restart Docker |

---

## 📊 Monitoring

```bash
# Logs
docker logs -f sorupilot

# Health check
curl https://vekil.siyahkare.com/health

# Bot status
curl -X POST https://api.telegram.org/bot{BOT_TOKEN}/getMe
```

---

## 🔐 Security

- [ ] BOT_TOKEN never in git
- [ ] LLM_API_KEY never in git
- [ ] HTTPS enforced
- [ ] Rate limiting configured
- [ ] Database backups setup

---

## 📅 Next: Trendyol Integration (Phase 2)

After deployment works:
- [ ] Get Trendyol API credentials
- [ ] OAuth implementation
- [ ] Product catalog sync
- [ ] Knowledge base auto-populate

---

**Status:** Ready for BARON to deploy

**Timeline:** ~15 min for Railway, ~30 min for self-hosted

**Cost:** Railway ~$5-50/mo, Cloudflare free tier
