#!/usr/bin/env bash
# SiyahKare uygulamalarını bu Mac'te çalıştırır ve Cloudflare Tunnel ile yayınlar:
#   https://vekil.siyahkare.com  (Vekil)
#   https://stars.siyahkare.com  (Stars satış sitesi + demo mağaza)
#   https://site.siyahkare.com   (kurumsal site taslağı, SiyahKare/SK2026)
#   (siyahkare.com ana alan adı Vercel'deki Sanal Devlet portalına bağlı; bu betik ona dokunmaz)
#
# Kullanım:  bash deploy/mac.sh
# Tekrar çalıştırmak güvenlidir: kodu günceller, ayarları korur, servisleri yeniden başlatır.
set -euo pipefail

BASE="$HOME/siyahkare-apps"
TUNNEL_NAME="siyahkare-apps"
VEKIL_HOST="vekil.siyahkare.com"; VEKIL_PORT=8701
STARS_HOST="stars.siyahkare.com"; STARS_PORT=8702
SITE_HOST="site.siyahkare.com"; SITE_PORT=8703
SITE_BRANCH="siyahkare-com-yayin"   # birleştirilince main'e düşer
AGENTS="$HOME/Library/LaunchAgents"
UIDN="$(id -u)"

say()  { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
die()  { printf "\n\033[31m✗ %s\033[0m\n" "$*"; exit 1; }

[ "$(uname)" = "Darwin" ] || die "Bu betik macOS içindir. Linux sunucuda deploy/install.sh kullan."

# ------------------------------------------------------------------ araçlar
say "Araçlar kontrol ediliyor"
command -v brew >/dev/null || die "Homebrew gerekli: https://brew.sh"
command -v git >/dev/null || brew install git
command -v cloudflared >/dev/null || brew install cloudflared
command -v npm >/dev/null || brew install node
PY=""
for c in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then brew install python@3.12; PY="$(brew --prefix)/bin/python3.12"; fi
ok "python: $PY ($("$PY" --version))"
ok "cloudflared: $(cloudflared --version 2>&1 | head -1)"

mkdir -p "$BASE/logs" "$AGENTS"

ask_early() { local v; read -rp "  $1: " v </dev/tty; printf "%s" "$v"; }
if [ -f "$BASE/vekil/.env" ]; then
  INSTALL_VEKIL=1
else
  say "Kurulum kapsamı"
  echo "  Stars + kurumsal site: bot token yeter. Vekil ayrıca kendi botunu ve bir AI anahtarı ister."
  ANS="$(ask_early 'Vekil de şimdi kurulsun mu? [e/H]')"
  if [[ "$ANS" =~ ^[eEyY] ]]; then INSTALL_VEKIL=1; else INSTALL_VEKIL=0; fi
fi

# ------------------------------------------------------------------ kod
fetch() { # repo dir
  if [ -d "$BASE/$2/.git" ]; then
    git -C "$BASE/$2" pull --ff-only -q && ok "$2 güncellendi"
  else
    git clone -q "https://github.com/onurmutlu/$1" "$BASE/$2" && ok "$2 indirildi"
  fi
}
say "Kod indiriliyor ($BASE)"
fetch vekil vekil
fetch stars stars
if [ -d "$BASE/site/.git" ]; then
  git -C "$BASE/site" pull --ff-only -q && ok "site güncellendi"
else
  git clone -q -b "$SITE_BRANCH" https://github.com/SiyahKare/SK2026 "$BASE/site" 2>/dev/null \
    || git clone -q https://github.com/SiyahKare/SK2026 "$BASE/site"
  ok "site indirildi ($(git -C "$BASE/site" branch --show-current))"
fi

venv() { # dir
  [ -x "$BASE/$1/.venv/bin/python" ] || "$PY" -m venv "$BASE/$1/.venv"
  "$BASE/$1/.venv/bin/pip" install -q --upgrade pip
  "$BASE/$1/.venv/bin/pip" install -q -r "$BASE/$1/requirements.txt" "python-dotenv[cli]"
  ok "$1 bağımlılıkları kuruldu"
}
say "Python ortamları hazırlanıyor"
[ "$INSTALL_VEKIL" = 1 ] && venv vekil
venv stars
say "Kurumsal site derleniyor"
( cd "$BASE/site" && npm install --no-audit --no-fund --silent && npm run build --silent ) >/dev/null
[ -f "$BASE/site/dist/index.html" ] && ok "siyahkare.com derlendi" || die "Site derlenemedi: cd $BASE/site && npm run build"

# ------------------------------------------------------------------ ayarlar
set_kv() { # file key value  (değerleri ekrana yazmadan .env'e işler)
  "$PY" - "$1" "$2" "$3" <<'PY'
import pathlib, re, sys
path, key, value = sys.argv[1:]
p = pathlib.Path(path)
text = p.read_text() if p.exists() else ""
line = f"{key}={value}"
if re.search(rf"^{re.escape(key)}=", text, re.M):
    text = re.sub(rf"^{re.escape(key)}=.*$", lambda _m: line, text, flags=re.M)
else:
    text = text.rstrip("\n") + "\n" + line + "\n"
p.write_text(text)
PY
}
get_kv() { grep -E "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- || true; }
secret() { "$PY" -c "import secrets; print(secrets.token_urlsafe(32))"; }
ask_secret() { local v; read -rsp "  $1: " v </dev/tty; echo >&2; printf "%s" "$v"; }
ask() { local v; read -rp "  $1: " v </dev/tty; printf "%s" "$v"; }

VENV_FILE="$BASE/vekil/.env"
SENV_FILE="$BASE/stars/.env"
CONTACT=""
if [ ! -f "$VENV_FILE" ] || [ ! -f "$SENV_FILE" ]; then
  say "İletişim"
  CONTACT="$(ask 'Müşterilerin sana yazacağı Telegram kullanıcı adı ya da adresi (ör. @kullaniciadi)')"
  case "$CONTACT" in
    "") ;;
    https://*) ;;
    @*) CONTACT="https://t.me/${CONTACT#@}" ;;
    t.me/*|telegram.me/*) CONTACT="https://$CONTACT" ;;
    *) CONTACT="https://t.me/$CONTACT" ;;
  esac
fi

if [ "$INSTALL_VEKIL" = 1 ]; then
say "Vekil ayarları"
if [ ! -f "$VENV_FILE" ]; then
  cp "$BASE/vekil/.env.example" "$VENV_FILE"
  echo "  @BotFather'da Vekil için bot oluştur; Bot Settings > Business Mode'u aç; /setdomain ile $VEKIL_HOST gir."
  set_kv "$VENV_FILE" BOT_TOKEN "$(ask_secret 'Vekil bot token (görünmez)')"
  set_kv "$VENV_FILE" BOT_USERNAME "$(ask 'Vekil bot kullanıcı adı (@ olmadan)')"
  PROVIDER="$(ask 'AI sağlayıcısı [anthropic/openai/echo] (boş = anthropic)')"; PROVIDER="${PROVIDER:-anthropic}"
  set_kv "$VENV_FILE" LLM_PROVIDER "$PROVIDER"
  if [ "$PROVIDER" != "echo" ]; then
    set_kv "$VENV_FILE" LLM_API_KEY "$(ask_secret 'AI API anahtarı (görünmez)')"
    MODEL="$(ask 'Model (boş = claude-haiku-5-5)')"; set_kv "$VENV_FILE" LLM_MODEL "${MODEL:-claude-haiku-5-5}"
  fi
  set_kv "$VENV_FILE" ADMIN_IDS "$(ask 'Senin Telegram kullanıcı ID numaran (iade komutları için)')"
  [ -n "$CONTACT" ] && set_kv "$VENV_FILE" SUPPORT_TEXT "Ödeme ve hesap desteği: $CONTACT"
  set_kv "$VENV_FILE" WEBHOOK_SECRET "$(secret)"
  set_kv "$VENV_FILE" DB_PATH "$BASE/vekil/data/vekil.sqlite3"
  chmod 600 "$VENV_FILE"
  ok "Vekil .env oluşturuldu"
else
  ok "Vekil .env mevcut, korunuyor"
fi
set_kv "$VENV_FILE" WEBAPP_URL "https://$VEKIL_HOST"
fi

say "Stars ayarları"
if [ ! -f "$SENV_FILE" ]; then
  cp "$BASE/stars/.env.example" "$SENV_FILE"
  echo "  @BotFather'da Stars demo mağazası için ayrı bir bot oluştur."
  set_kv "$SENV_FILE" BOT_TOKEN "$(ask_secret 'Stars bot token (görünmez)')"
  set_kv "$SENV_FILE" BOT_USERNAME "$(ask 'Stars bot kullanıcı adı (@ olmadan)')"
  if [ -n "$CONTACT" ]; then
    set_kv "$SENV_FILE" CONTACT_URL "$CONTACT"
    set_kv "$SENV_FILE" SUPPORT_TEXT "Ödeme desteği: $CONTACT"
  fi
  set_kv "$SENV_FILE" TERMS_TEXT "Demo ürün: 1 Star karşılığı dijital içerik, ödemeden hemen sonra teslim edilir. İade için /paysupport."
  # Demo mağaza 1 ⭐'lık ürünle satışa açık başlar: sitedeki "Canlı demo" gerçekten çalışsın.
  set_kv "$SENV_FILE" SALES_ENABLED true
  ADMINS="$(get_kv "$VENV_FILE" ADMIN_IDS)"
  [ -n "$ADMINS" ] || ADMINS="$(ask 'Senin Telegram kullanıcı ID numaran (iade komutları için; @userinfobot söyler)')"
  set_kv "$SENV_FILE" ADMIN_IDS "$ADMINS"
  set_kv "$SENV_FILE" SHOP_NAME "SiyahKare Stars Demo"
  set_kv "$SENV_FILE" WEBHOOK_SECRET "$(secret)"
  set_kv "$SENV_FILE" DB_PATH "$BASE/stars/data/shop.sqlite3"
  set_kv "$SENV_FILE" PRODUCTS_PATH "$BASE/stars/products.json"
  chmod 600 "$SENV_FILE"
  ok "Stars .env oluşturuldu"
else
  ok "Stars .env mevcut, korunuyor"
fi
set_kv "$SENV_FILE" WEBAPP_URL "https://$STARS_HOST"
if [ ! -f "$BASE/stars/products.json" ]; then
  cat > "$BASE/stars/products.json" <<'JSON'
[
  {"id": "demo-guide", "title": "Demo: Stars Rehberi", "description": "Stars ödemesini kendin dene. 1 Star; içerik ödemeden hemen sonra açılır.", "stars": 1,
   "content": "Teşekkürler! Bu bir demo satın almasıydı. Botun için Stars kurulumu: https://stars.siyahkare.com"}
]
JSON
  ok "Demo ürün eklendi (1 ⭐)"
fi

# ------------------------------------------------------------------ cloudflare tunnel
say "Cloudflare Tunnel"
if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "  Tarayıcı açılacak: siyahkare.com alan adını seçip yetki ver."
  cloudflared tunnel login
fi
TUNNEL_ID="$(cloudflared tunnel list -o json 2>/dev/null | "$PY" -c "
import json,sys
for t in json.load(sys.stdin) or []:
    if t.get('name') == '$TUNNEL_NAME' and not t.get('deleted_at', '').startswith('2'):
        print(t['id']); break" || true)"
if [ -z "$TUNNEL_ID" ]; then
  cloudflared tunnel create "$TUNNEL_NAME" >/dev/null
  TUNNEL_ID="$(cloudflared tunnel list -o json | "$PY" -c "
import json,sys
print(next(t['id'] for t in json.load(sys.stdin) if t['name'] == '$TUNNEL_NAME'))")"
  ok "Tunnel oluşturuldu: $TUNNEL_NAME"
else
  ok "Tunnel mevcut: $TUNNEL_NAME"
fi
CREDS="$HOME/.cloudflared/$TUNNEL_ID.json"
[ -f "$CREDS" ] || die "Tunnel kimlik dosyası yok: $CREDS. 'cloudflared tunnel delete $TUNNEL_NAME' ile silip betiği tekrar çalıştır."

HOSTS=("$STARS_HOST" "$SITE_HOST"); [ "$INSTALL_VEKIL" = 1 ] && HOSTS=("$VEKIL_HOST" "${HOSTS[@]}")
for host in "${HOSTS[@]}"; do
  if cloudflared tunnel route dns "$TUNNEL_NAME" "$host" >/dev/null 2>&1; then
    ok "DNS: $host → $TUNNEL_NAME"
  else
    warn "$host için DNS kaydı eklenemedi (büyük ihtimalle zaten bir kayıt var)."
    warn "Cloudflare DNS'te $host kaydını sil ya da CNAME olarak $TUNNEL_ID.cfargotunnel.com yap, sonra betiği tekrar çalıştır."
  fi
done

cat > "$BASE/cloudflared.yml" <<YML
tunnel: $TUNNEL_ID
credentials-file: $CREDS
ingress:
$( [ "$INSTALL_VEKIL" = 1 ] && printf '  - hostname: %s\n    service: http://127.0.0.1:%s\n' "$VEKIL_HOST" "$VEKIL_PORT" )
  - hostname: $STARS_HOST
    service: http://127.0.0.1:$STARS_PORT
  - hostname: $SITE_HOST
    service: http://127.0.0.1:$SITE_PORT
  - service: http_status:404
YML
cloudflared tunnel --config "$BASE/cloudflared.yml" ingress validate >/dev/null && ok "Tunnel ayarı geçerli"

# ------------------------------------------------------------------ servisler (launchd)
plist() { # label workdir logname args...
  local label="$1" dir="$2" log="$3"; shift 3
  local args=""; for a in "$@"; do args="$args<string>$a</string>"; done
  cat > "$AGENTS/$label.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>$args</array>
  <key>WorkingDirectory</key><string>$dir</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$BASE/logs/$log.log</string>
  <key>StandardErrorPath</key><string>$BASE/logs/$log.log</string>
</dict></plist>
PL
  launchctl bootout "gui/$UIDN/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UIDN" "$AGENTS/$label.plist"
}
say "Servisler başlatılıyor (bilgisayar açıldığında otomatik başlar)"
if [ "$INSTALL_VEKIL" = 1 ]; then
  plist com.siyahkare.vekil "$BASE/vekil" vekil \
    "$BASE/vekil/.venv/bin/uvicorn" app.main:app --factory --host 127.0.0.1 --port "$VEKIL_PORT" --env-file "$VENV_FILE" --proxy-headers
fi
plist com.siyahkare.stars "$BASE/stars" stars \
  "$BASE/stars/.venv/bin/uvicorn" app.main:app --factory --host 127.0.0.1 --port "$STARS_PORT" --env-file "$SENV_FILE" --proxy-headers
plist com.siyahkare.site "$BASE/site/dist" site \
  "$PY" -m http.server "$SITE_PORT" --bind 127.0.0.1 --directory "$BASE/site/dist"
plist com.siyahkare.tunnel "$BASE" tunnel \
  "$(command -v cloudflared)" tunnel --no-autoupdate --config "$BASE/cloudflared.yml" run

wait_ok() { # url name
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "$1" >/dev/null 2>&1; then ok "$2 çalışıyor"; return 0; fi
    sleep 2
  done
  warn "$2 yanıt vermedi. Log: $BASE/logs/"; return 1
}
if [ "$INSTALL_VEKIL" = 1 ]; then wait_ok "http://127.0.0.1:$VEKIL_PORT/health" "Vekil (yerel)" || tail -20 "$BASE/logs/vekil.log"; fi
wait_ok "http://127.0.0.1:$STARS_PORT/health" "Stars (yerel)" || tail -20 "$BASE/logs/stars.log"
wait_ok "http://127.0.0.1:$SITE_PORT/" "siyahkare.com (yerel)" || tail -20 "$BASE/logs/site.log"

say "İnternetten erişim kontrolü (DNS yayılması 1-2 dakika sürebilir)"
PUBLIC_OK=1
if [ "$INSTALL_VEKIL" = 1 ]; then wait_ok "https://$VEKIL_HOST/health" "https://$VEKIL_HOST" || PUBLIC_OK=0; fi
wait_ok "https://$STARS_HOST/health" "https://$STARS_HOST" || PUBLIC_OK=0
wait_ok "https://$SITE_HOST/" "https://$SITE_HOST" || PUBLIC_OK=0

# ------------------------------------------------------------------ telegram
say "Telegram botları bağlanıyor"
APPS=(stars); [ "$INSTALL_VEKIL" = 1 ] && APPS=(vekil stars)
for app in "${APPS[@]}"; do
  envf="$BASE/$app/.env"
  ( cd "$BASE/$app" && "$BASE/$app/.venv/bin/dotenv" -f "$envf" run -- "$BASE/$app/.venv/bin/python" -m app.cli setup ) \
    && ok "$app botu hazır" || warn "$app botu ayarlanamadı. Sonra: cd $BASE/$app && .venv/bin/dotenv -f .env run -- .venv/bin/python -m app.cli setup"
done

# ------------------------------------------------------------------ uyku
say "Uyku ayarı"
echo "  Bilgisayar uykuya geçerse siteler kapanır."
ANS="$(ask 'Şarjdayken uykuyu engelleyen servis kurulsun mu? [e/H]')"
if [[ "$ANS" =~ ^[eEyY] ]]; then
  plist com.siyahkare.awake "$BASE" awake /usr/bin/caffeinate -s
  ok "Şarjdayken uyku engellendi (kaldırmak için: launchctl bootout gui/$UIDN/com.siyahkare.awake)"
fi

say "Bitti"
[ "$INSTALL_VEKIL" = 1 ] && echo "  Vekil:  https://$VEKIL_HOST   (panel: /app)"
echo "  Stars:  https://$STARS_HOST   (demo mağaza: /app)"
echo "  Site:   https://$SITE_HOST"
[ "$PUBLIC_OK" = 1 ] || warn "Siteler henüz dışarıdan açılmadı; birkaç dakika sonra tekrar dene."
cat <<TXT

  Stars demo mağazası 1 ⭐'lık demo ürünle açık. Vekil'de Pro satışı KAPALI başlar; açmak için:
    $BASE/<uygulama>/.env  içinde SALES_ENABLED=true yap, sonra:
    launchctl kickstart -k gui/$UIDN/com.siyahkare.vekil   (ya da .stars)

  Loglar:     tail -f $BASE/logs/*.log
  Durdurmak:  launchctl bootout gui/$UIDN/com.siyahkare.vekil   (stars, tunnel için de aynı)
TXT
