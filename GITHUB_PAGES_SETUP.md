# GitHub Pages Deployment for SoruPilot Panel

## 📋 BARON'un yapması gerekenler

### 1️⃣ Push to GitHub

```bash
# BARON'ın makinesinde:
cd vekil
git checkout sorupilot
git push -u origin sorupilot
```

### 2️⃣ Enable GitHub Pages

1. GitHub: github.com/onurmutlu/vekil
2. Settings → Pages
3. Source: Deploy from branch
4. Branch: sorupilot
5. Folder: / (root) or /webapp
6. Save

### 3️⃣ Configure Custom Domain

1. Settings → Pages → Custom domain
2. Enter: vekil.siyahkare.com
3. Save

### 4️⃣ Cloudflare DNS Setup

```dns
vekil.siyahkare.com  CNAME  onurmutlu.github.io
```

Wait 5-10 min for DNS propagation.

### 5️⃣ Enable HTTPS

GitHub Pages will auto-generate SSL cert.
Check: Settings → Pages → Enforce HTTPS

---

## 🏗️ Architecture

```
GitHub Pages (Web Panel)
  ├─ HTML/CSS/JS (vekil.siyahkare.com)
  └─ API calls to → Backend (Railway/Cloud Run)

Backend (Railway/Cloud Run)
  ├─ Telegram Webhook
  ├─ Claude LLM
  ├─ SQLite Database
  └─ API: /api/*, /telegram/webhook
```

---

## 📡 Update API Endpoint

In `webapp/index.html` or JS:

```javascript
// Before:
const API_URL = "http://localhost:8000"

// After:
const API_URL = "https://your-railway-url.railway.app"
// or
const API_URL = "https://your-cloudrun-url.run.app"
```

---

## ✅ Verification

- [ ] Push succeeded: `git log --oneline -3`
- [ ] GitHub Pages enabled
- [ ] Custom domain set
- [ ] DNS resolves: `nslookup vekil.siyahkare.com`
- [ ] HTTPS works: https://vekil.siyahkare.com (green lock)
- [ ] API connected: Panel shows data from backend

---

## 🚀 Final Deployment Steps

### Step 1: Backend (Railway)
```bash
./deploy.sh railway
# → Get Railway API URL
```

### Step 2: Update Panel API
Edit `webapp/index.html`:
```javascript
const API_BASE = "https://railway-api-url.railway.app";
```

### Step 3: Push & Deploy
```bash
git add .
git commit -m "config: Update API endpoint for production"
git push origin sorupilot
```

GitHub Pages auto-deploys.

### Step 4: Setup Webhook
```bash
# On Railway app:
python -m app.cli setup
# → Registers webhook with Telegram
```

---

## 🎯 Final URLs

- **Web Panel:** https://vekil.siyahkare.com
- **API Backend:** https://railway-url.railway.app
- **Telegram Bot:** @SoruPilotBot

---

**Status:** Ready to deploy!

Timeline:
- Push: 1 min
- GitHub Pages: Automatic
- DNS: 5-10 min
- Full deployment: ~15 min
