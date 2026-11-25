#!/usr/bin/env bash
# Vekil kurulumu: Docker + Cloudflare Tunnel ile https://vekil.siyahkare.com
# Kullanım (Ubuntu/Debian VPS ya da Docker kurulu Mac):
#   git clone https://github.com/onurmutlu/vekil && cd vekil && bash deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf "\n\033[1m%s\033[0m\n" "$*"; }

if ! command -v docker >/dev/null 2>&1; then
  if [ "$(uname)" = "Linux" ]; then
    say "Docker kuruluyor…"
    curl -fsSL https://get.docker.com | sh
  else
    echo "Docker bulunamadı. Docker Desktop'ı kur ve yeniden çalıştır."; exit 1
  fi
fi

if [ ! -f .env ]; then
  say "Ayarlar (.env) oluşturuluyor. Değerler sadece bu sunucuda kalır."
  cp .env.example .env
  read -rsp "BotFather bot token'ı (ekranda görünmez): " BOT_TOKEN; echo
  read -rp "Bot kullanıcı adı (@ olmadan): " BOT_USERNAME
  read -rsp "Cloudflare Tunnel token'ı (ekranda görünmez): " TUNNEL_TOKEN; echo
  read -rp "Admin Telegram kullanıcı ID'n (iade/sorun komutları için): " ADMIN_IDS
  read -rp "AI sağlayıcısı [anthropic/openai]: " LLM_PROVIDER
  read -rsp "AI API anahtarı (ekranda görünmez): " LLM_API_KEY; echo
  read -rp "Model adı [anthropic için claude-haiku-5-5]: " LLM_MODEL
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -hex 24)
  set_kv() { # set KEY=VALUE in .env without echoing secrets
    python3 - "$1" "$2" <<'PY'
import sys, re, pathlib
key, value = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env"); text = p.read_text()
line = f"{key}={value}"
text = re.sub(rf"^{key}=.*$", lambda _m: line, text, flags=re.M) if re.search(rf"^{key}=", text, re.M) else text + "\n" + line + "\n"
p.write_text(text)
PY
  }
  set_kv BOT_TOKEN "$BOT_TOKEN"
  set_kv BOT_USERNAME "$BOT_USERNAME"
  set_kv WEBHOOK_SECRET "$SECRET"
  set_kv WEBAPP_URL "https://vekil.siyahkare.com"
  set_kv TUNNEL_TOKEN "$TUNNEL_TOKEN"
  set_kv ADMIN_IDS "$ADMIN_IDS"
  set_kv LLM_PROVIDER "${LLM_PROVIDER:-anthropic}"
  set_kv LLM_API_KEY "$LLM_API_KEY"
  set_kv LLM_MODEL "${LLM_MODEL:-claude-haiku-5-5}"
  chmod 600 .env
fi

say "Servis başlatılıyor…"
docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml up -d --build

say "Sağlık kontrolü…"
for i in $(seq 1 30); do
  if docker compose exec -T vekil python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
    echo "Uygulama çalışıyor."; break
  fi
  sleep 2
done

say "Telegram'a bağlanıyor (webhook, menü butonu, komutlar)…"
echo "Not: https://vekil.siyahkare.com adresinin açılması için Cloudflare'de tunnel'ın Public Hostname'i tanımlı olmalı."
docker compose exec -T vekil python -m app.cli setup || echo "Setup başarısız. Adres açılınca tekrar çalıştır: docker compose exec vekil python -m app.cli setup"

say "Bitti: https://vekil.siyahkare.com"
echo "Satış kapalı başlar. Test ettikten sonra .env içinde SALES_ENABLED=true yapıp: docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml up -d"
