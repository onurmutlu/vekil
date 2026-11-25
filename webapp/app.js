(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  let state = null;
  let thread = [];
  const inTelegram = Boolean(tg && tg.initData);
  const TOKEN_KEY = "vekil.session";

  // Browser storage can be missing or blocked: never let that break the panel.
  const storage = {
    get() { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (_) { return ""; } },
    set(v) { try { localStorage.setItem(TOKEN_KEY, v); } catch (_) { /* session only for this page */ } },
    clear() { try { localStorage.removeItem(TOKEN_KEY); } catch (_) { /* ignore */ } },
  };
  let session = storage.get();

  function authHeaders() {
    if (inTelegram) return { "X-Telegram-Init-Data": tg.initData };
    return session ? { Authorization: `Bearer ${session}` } : {};
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...authHeaders() },
    });
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && !inTelegram && path !== "/api/auth/telegram") {
      session = "";
      storage.clear();
      showLogin(body.detail);
      throw new Error(body.detail || "Giriş yapman gerekiyor.");
    }
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? "Girilen değerleri kontrol et." : body.detail;
      throw new Error(detail || "Bir şeyler ters gitti. Tekrar dene.");
    }
    return body;
  }

  function toast(message) {
    const node = $("toast");
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { node.hidden = true; }, 3200);
  }

  const haptic = (kind) => inTelegram && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(kind);
  const alertBox = (text) => (inTelegram ? tg.showAlert(text) : window.alert(text));

  function show(view) {
    for (const name of ["setup", "try", "chats", "plan"]) $(`view-${name}`).hidden = name !== view;
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === view));
    if (view === "chats") loadChats();
  }

  // ------------------------------------------------------------ state rendering
  function render(next) {
    state = next;
    $("product").textContent = state.product_name || "Vekil";
    $("bot-handle").textContent = state.bot_username ? `@${state.bot_username}` : "bu botu";

    const ready = state.connected && state.can_reply;
    $("connect-card").hidden = ready;
    $("connect-state").textContent = !state.connected
      ? "Henüz bağlı değil. Bağladığında bota bildirim gelecek."
      : "Bağlı, ama 'Mesajlara cevap ver' izni kapalı.";

    const toggle = $("active");
    toggle.checked = state.active;
    toggle.disabled = !ready;
    $("status-line").textContent = !ready ? "Kurulum bekliyor"
      : state.active ? `Açık · ${state.quota.left} yanıt hakkı kaldı` : "Kapalı · müşterilere cevap vermiyor";

    const form = $("profile");
    for (const [key, value] of Object.entries(state.profile)) {
      if (form.elements[key] && document.activeElement !== form.elements[key]) form.elements[key].value = value;
    }
    renderPlan();
  }

  function renderPlan() {
    const q = state.quota;
    const used = q.limit - q.left;
    $("plan-title").textContent = q.plan === "paid" ? "Pro plan" : "Deneme";
    $("meter-fill").style.width = `${q.limit ? Math.min(100, (used / q.limit) * 100) : 100}%`;
    $("plan-usage").textContent = `${used} / ${q.limit} AI yanıtı kullanıldı`;
    $("plan-until").textContent = q.plan_until
      ? `Yenileme: ${new Date(q.plan_until * 1000).toLocaleDateString("tr-TR", { day: "numeric", month: "long" })}` : "";
    $("buy-card").hidden = q.plan === "paid" || !state.plan.sales_enabled;
    $("plan-price").textContent = String(state.plan.stars);
    const features = $("plan-features");
    features.replaceChildren(...[
      `Ayda ${state.plan.replies} AI yanıtı`,
      "Sınırsız sohbet ve müşteri",
      "Yetkiliye devretme bildirimleri",
    ].map((text) => el("li", "", text)));
  }

  // ------------------------------------------------------------ actions
  async function saveProfile(event) {
    event.preventDefault();
    const form = event.target;
    const body = Object.fromEntries(new FormData(form).entries());
    body.pause_minutes = Number(body.pause_minutes || 30);
    $("save").disabled = true;
    try {
      render(await api("/api/profile", { method: "PUT", body: JSON.stringify(body) }));
      haptic("success");
      toast("Kaydedildi");
    } catch (error) {
      toast(error.message);
    } finally {
      $("save").disabled = false;
    }
  }

  async function toggleActive(event) {
    const wanted = event.target.checked;
    try {
      render(await api("/api/active", { method: "POST", body: JSON.stringify({ active: wanted }) }));
      haptic("success");
      toast(wanted ? "Asistan açıldı" : "Asistan kapatıldı");
    } catch (error) {
      event.target.checked = !wanted;
      toast(error.message);
    }
  }

  function renderThread() {
    const box = $("thread");
    if (!thread.length) {
      box.replaceChildren(el("p", "muted small", "Henüz mesaj yok."));
      return;
    }
    box.replaceChildren(...thread.map((m) => el("div", `bubble ${m.from}`, m.text)));
    box.scrollTop = box.scrollHeight;
  }

  async function sendTry(event) {
    event.preventDefault();
    const input = $("try-input");
    const text = input.value.trim();
    if (!text) return;
    thread.push({ from: "customer", text });
    input.value = "";
    renderThread();
    const typing = el("div", "bubble assistant", "…");
    $("thread").append(typing);
    try {
      const messages = thread.filter((m) => m.from !== "system");
      const result = await api("/api/playground", { method: "POST", body: JSON.stringify({ messages }) });
      if (result.reply) thread.push({ from: "assistant", text: result.reply });
      if (result.handoff) thread.push({ from: "system", text: `Burada sana devrederdi: ${result.reason || "neden belirtilmedi"}` });
    } catch (error) {
      thread.pop();
      toast(error.message);
    }
    renderThread();
  }

  async function loadChats() {
    const list = $("chat-list");
    try {
      const chats = await api("/api/chats");
      const waiting = chats.filter((c) => c.status === "handoff").length;
      $("handoff-count").hidden = !waiting;
      $("handoff-count").textContent = String(waiting);
      if (!chats.length) {
        list.replaceChildren(el("div", "empty", "Asistan açıldığında müşteri sohbetleri burada görünür."));
        return;
      }
      list.replaceChildren(...chats.map(chatCard));
    } catch (error) {
      list.replaceChildren(el("div", "empty", error.message));
    }
  }

  function chatCard(chat) {
    const card = el("article", "chat");
    const head = el("div", "chat-head");
    head.append(el("span", "chat-name", chat.name || "Müşteri") );
    const badge = chat.status === "handoff" ? el("span", "badge handoff", "Seni bekliyor")
      : chat.paused ? el("span", "badge paused", "Sen yazdın · asistan susuyor")
      : el("span", "badge", "Asistan cevaplıyor");
    head.append(badge);
    card.append(head);
    if (chat.username) card.append(el("span", "muted small", `@${chat.username}`));
    card.append(el("p", "muted small", chat.status === "handoff" && chat.reason ? `Neden: ${chat.reason}` : chat.last_text));
    if (chat.status === "handoff" || chat.paused) {
      const resume = el("button", "btn ghost", "Asistan devam etsin");
      resume.addEventListener("click", async () => {
        try {
          await api(`/api/chats/${chat.chat_id}/resume`, { method: "POST" });
          haptic("success");
          loadChats();
        } catch (error) {
          toast(error.message);
        }
      });
      card.append(resume);
    }
    return card;
  }

  async function buy() {
    $("buy").disabled = true;
    const waitForPlan = async (tries) => {
      for (let i = 0; i < tries; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        const next = await api("/api/me").catch(() => null);
        if (next && next.quota.plan === "paid") { render(next); toast("Planın aktif ⭐"); return; }
      }
    };
    try {
      const { invoice_link: link } = await api("/api/billing/invoice", { method: "POST" });
      if (!inTelegram) {
        // On the web the Stars invoice opens in the Telegram app; we watch for the payment here.
        window.open(link, "_blank", "noopener");
        $("buy").disabled = false;
        toast("Ödemeyi Telegram'da tamamla, bu sayfa kendini güncelleyecek.");
        waitForPlan(60);
        return;
      }
      tg.openInvoice(link, async (status) => {
        $("buy").disabled = false;
        if (status === "paid") {
          haptic("success");
          toast("Teşekkürler! Planın birkaç saniye içinde aktif olacak.");
          waitForPlan(8);
        } else if (status === "failed") {
          toast("Ödeme tamamlanamadı.");
        }
      });
    } catch (error) {
      $("buy").disabled = false;
      toast(error.message);
    }
  }

  // ------------------------------------------------------------ web login
  function showLogin(note) {
    document.querySelectorAll(".view").forEach((v) => { v.hidden = true; });
    document.querySelector(".tabs").hidden = true;
    $("active").parentElement.hidden = true;
    $("status-line").textContent = "Giriş yap";
    $("login").hidden = false;
    $("login-note").textContent = note || "";
    if ($("login-widget").childElementCount) return;
    fetch("/api/public").then((r) => r.json()).then((cfg) => {
      if (!cfg.bot_username) {
        $("login-note").textContent = "Giriş henüz yapılandırılmadı (BOT_USERNAME).";
        return;
      }
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://telegram.org/js/telegram-widget.js?22";
      script.dataset.telegramLogin = cfg.bot_username;
      script.dataset.size = "large";
      script.dataset.radius = "10";
      script.dataset.requestAccess = "write";  // lets the bot send hand-off notifications
      script.dataset.onauth = "vekilAuth(user)";
      $("login-widget").append(script);
    }).catch(() => { $("login-note").textContent = "Giriş yüklenemedi, sayfayı yenile."; });
  }

  window.vekilAuth = async (user) => {
    try {
      const { token } = await api("/api/auth/telegram", { method: "POST", body: JSON.stringify(user) });
      session = token;
      storage.set(token);
      document.querySelectorAll(".web-only").forEach((n) => { n.hidden = false; });
      $("login").hidden = true;
      document.querySelector(".tabs").hidden = false;
      $("active").parentElement.hidden = false;
      show("setup");
      await start();
    } catch (error) {
      $("login-note").textContent = error.message;
    }
  };

  // ------------------------------------------------------------ boot
  async function start() {
    renderThread();
    try {
      render(await api("/api/me"));
      loadChats();
    } catch (error) {
      if (inTelegram) $("status-line").textContent = error.message;
    }
  }

  function boot() {
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => show(tab.dataset.tab)));
    $("profile").addEventListener("submit", saveProfile);
    $("active").addEventListener("change", toggleActive);
    $("try-form").addEventListener("submit", sendTry);
    $("try-reset").addEventListener("click", () => { thread = []; renderThread(); });
    $("buy").addEventListener("click", buy);
    $("support").addEventListener("click", () => alertBox((state && state.support) || "Destek bilgisi yok."));
    $("terms").addEventListener("click", () => alertBox((state && state.terms) || "Koşullar tanımlanmadı."));

    if (inTelegram) {
      tg.ready();
      tg.expand();
      start();
      return;
    }
    document.body.classList.add("web");
    if (session) document.querySelectorAll(".web-only").forEach((n) => { n.hidden = false; });
    $("logout").addEventListener("click", () => { session = ""; storage.clear(); window.location.reload(); });
    if (session) start(); else showLogin();
  }

  boot();
})();
