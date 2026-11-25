# Yayına alma: https://vekil.siyahkare.com

Docker + Cloudflare Tunnel. Sunucuda port açılmaz, HTTPS'i Cloudflare sağlar.
Bir VPS'te (önerilen: Ubuntu, 1 vCPU / 1 GB yeterli) ya da Docker kurulu bir bilgisayarda çalışır.

## 1. Telegram botu
@BotFather → `/newbot` → token'ı al.
Sonra: `/mybots` → bot → **Bot Settings → Business Mode → Turn on** ve **`/setdomain` → `vekil.siyahkare.com`** (web girişi için).

## 2. Cloudflare Tunnel
1. Cloudflare → Zero Trust → Networks → Tunnels → **Create a tunnel** → Cloudflared → ad: `vekil`.
2. Kurulum ekranındaki token'ı kopyala (`eyJ...` ile başlayan uzun değer). Komutu çalıştırma, token yeter.
3. **Public Hostname** ekle: Subdomain `vekil`, Domain `siyahkare.com`, Service `HTTP` → `vekil:8000`.

## 3. Sunucuda
```bash
git clone https://github.com/onurmutlu/vekil && cd vekil
bash deploy/install.sh
```
Kurulum bot token'ını, tunnel token'ını ve admin ID'ni sorar; webhook gizli değerini kendisi üretir.
Değerler sadece sunucudaki `.env` dosyasında kalır (izin: 600). Sonunda webhook ve menü butonu otomatik ayarlanır.

## 4. Kontrol
- https://vekil.siyahkare.com/health → `{"ok":true}`
- Telegram'da bota `/start` yaz.
- Satış kapalı başlar. Test ettikten sonra `.env` içinde `SALES_ENABLED=true` yap ve:
  `docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml up -d`

## Güncelleme ve yedek
```bash
git pull && docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml up -d --build
docker compose cp vekil:/srv/data ./yedek-$(date +%F)     # veritabanı yedeği
docker compose logs -f vekil                                # loglar
```
