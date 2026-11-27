# SoruPilot: Vercel Deployment

## 🚀 Quick Deploy (3 minutes)

### Step 1: Create Vercel Account
1. Go to https://vercel.com
2. Sign up or login with GitHub
3. Click "Import Project"

### Step 2: Connect GitHub Repository
1. Select: **github.com/onurmutlu/vekil**
2. Branch: **sorupilot**
3. Framework: **Other** (or leave blank)
4. Root Directory: **./webapp** (for frontend)

### Step 3: Configure & Deploy
1. Click "Deploy"
2. Wait for build to complete (2-3 min)
3. You'll get a vercel.app URL

### Step 4: Add Custom Domain
1. Project Settings → Domains
2. Add Domain: **vekil.siyahkare.com**
3. Copy CNAME value from Vercel
4. Go to Cloudflare and add CNAME record

### Step 5: Wait for DNS
- DNS propagation: 5-10 minutes
- Check: https://vekil.siyahkare.com (should work)

---

## 🔧 Backend API Configuration

**Problem:** Vercel hosts the **frontend** only. Backend needs to run separately.

### Solution:
1. Backend on Railway: `./deploy.sh railway`
2. Get Railway API URL
3. Update `webapp/index.html`:
   ```javascript
   const API_URL = "https://your-railway-url.railway.app"
   ```
4. Commit & push (auto-deploys via GitHub Actions)

---

## 📋 Final URLs

| Component | URL |
|-----------|-----|
| **Landing Page** | vekil.siyahkare.com (Vercel) |
| **Seller Panel** | vekil.siyahkare.com/app (Vercel) |
| **API Backend** | railway-url.railway.app |
| **Telegram Bot** | @SoruPilotBot |

---

## ✅ Verification

- [ ] Vercel project created
- [ ] GitHub connected (sorupilot branch)
- [ ] Deploy successful
- [ ] Custom domain added
- [ ] DNS resolves (wait 5-10 min)
- [ ] Landing page loads: vekil.siyahkare.com
- [ ] API endpoint configured
- [ ] Railway backend running
- [ ] Telegram webhook set up

---

## 🎯 Total Timeline

- Vercel: 3-5 min
- DNS: 5-10 min wait
- Railway: 10 min
- Webhook: 1 min
- **Total: ~20-25 min**

---

**Next:** Follow Step 1-5 above ↑

Questions? Use this guide or ask!
