# SoruPilot: Production Deployment Checklist

## ✅ Pre-Deployment (Local Testing)

- [ ] **BotFather Setup**
  - [ ] Create bot with @BotFather
  - [ ] Enable Business Mode in Bot Settings
  - [ ] Copy BOT_TOKEN to `.env`
  - [ ] Set webhook domain in BotFather

- [ ] **Environment Variables**
  - [ ] BOT_TOKEN = ✓
  - [ ] LLM_API_KEY (Anthropic) = ✓
  - [ ] WEBHOOK_SECRET = ✓ (random string)
  - [ ] WEBAPP_URL = ✓ (http://localhost:8000 for local)

- [ ] **Local Testing**
  ```bash
  ./deploy.sh docker
  # or: python -m app.cli poll
  ```
  - [ ] Bot responds in Telegram
  - [ ] Panel accessible at `/app`
  - [ ] Telegram Login works
  - [ ] Store settings save correctly
  - [ ] AI responses working

- [ ] **Database Check**
  - [ ] SQLite created: `data/sorupilot.db`
  - [ ] Tables initialized
  - [ ] No errors in logs

---

## 🚀 Production Deployment

### Option A: Cloud Run (Google Cloud)

```bash
# 1. Create GCP project
gcloud projects create sorupilot-prod

# 2. Enable APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# 3. Deploy
./deploy.sh cloudrun sorupilot-prod us-central1
```

**Post-Deploy:**
- [ ] Get Cloud Run URL
- [ ] Update `.env`: `WEBAPP_URL=https://sorupilot-xxx.run.app`
- [ ] Set webhook in BotFather with Cloud Run URL
- [ ] Test bot → should work

### Option B: Railway (Simpler)

```bash
npm install -g @railway/cli
railway link
./deploy.sh railway
```

**Post-Deploy:**
- [ ] Get Railway app URL
- [ ] Update BotFather webhook
- [ ] Test bot

### Option C: Replit (Simplest)

```bash
./deploy.sh replit
# App runs on Replit's URL automatically
```

---

## 📡 Webhook Configuration

**After deploying, run:**
```bash
python -m app.cli setup
```

This will:
- [ ] Register webhook with Telegram
- [ ] Set up menu button
- [ ] Configure bot commands

**Verify webhook:**
```bash
curl -X POST https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo
# Should show your webhook URL
```

---

## 🔐 Security Checklist

- [ ] BOT_TOKEN never committed to git
- [ ] LLM_API_KEY never committed to git
- [ ] `.env` in `.gitignore`
- [ ] WEBHOOK_SECRET is random (32+ chars)
- [ ] Database backups configured
- [ ] Rate limiting configured
- [ ] CORS properly set
- [ ] HTTPS enforced (production)

---

## 📊 Monitoring

**After deployment:**

```bash
# Check bot status
curl -X POST https://api.telegram.org/bot{BOT_TOKEN}/getMe

# Check webhook health
curl -X GET https://your-app-url/health

# View logs
# Cloud Run: gcloud run logs read sorupilot
# Railway: railway logs
# Replit: See console
```

---

## 💰 Cost Estimates

| Platform | Tier | Cost/mo | Notes |
|----------|------|---------|-------|
| Cloud Run | Always Free | $0 (up to 2M calls) | Best for scaling |
| Railway | Usage-based | ~$5-50 | Simple billing |
| Replit | Free | $0 | Good for MVP |
| Vercel (panel) | Free | $0 | Included |

---

## 🎯 Final Checklist

- [ ] Bot responding to messages
- [ ] Panel login working
- [ ] Store settings persistent
- [ ] AI generating responses
- [ ] Webhook registered
- [ ] Logs clear (no errors)
- [ ] Database persisted
- [ ] Ready for Trendyol integration

---

## 📋 Trendyol Integration (Phase 2)

After main deployment works:

- [ ] Get Trendyol API credentials
- [ ] Implement OAuth flow
- [ ] Sync product catalog
- [ ] Auto-populate knowledge base
- [ ] Add seller dashboard
- [ ] Testing with real Trendyol seller account

---

**Status:** Ready for deployment ✅

**Next:** Choose deployment option and run setup!
