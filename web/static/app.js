// MarketTracker Mini App — логика для UI «Ценолов», подключённая к backend API.
// Все функции глобальные (используются из onclick в разметке).

// ---------- Auth ----------
function authHeaders() {
  const h = { "Content-Type": "application/json" };
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg && tg.initData) {
    h["X-Telegram-Init-Data"] = tg.initData;
  } else {
    let uid = localStorage.getItem("mt_dev_uid");
    if (!uid) { uid = prompt("Dev: ваш telegram id?") || "0"; localStorage.setItem("mt_dev_uid", uid); }
    h["X-User-Id"] = uid;
  }
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { ...authHeaders(), ...(opts.headers || {}) } });
  if (!res.ok) {
    let msg = "Ошибка запроса";
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------- Helpers ----------
const money = n => (n == null || isNaN(n)) ? "—" : Math.round(n).toLocaleString("ru-RU") + " ₽";
const pct = n => (n == null || isNaN(n)) ? "0%" : (n > 0 ? "+" : "") + n.toLocaleString("ru-RU", { maximumFractionDigits: 1 }) + "%";
function escapeHtml(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
const icon = name => `<svg class="icon"><use href="#i-${name}"/></svg>`;

// ---------- State ----------
let items = [];
let activeFilter = "all";
let currentDetailId = null;
let toastTimer = null;

function mapTrack(t) {
  const price = t.current_price;
  const history = (t.history && t.history.length) ? t.history : (price != null ? [price] : []);
  const old = t.last_checked_price != null ? t.last_checked_price : history[0];
  const change = t.change_7d != null ? t.change_7d : 0;
  const target = t.target_price;
  return {
    id: t.id, name: t.title, market: t.marketplace, location: "",
    price, old, target, change, delta: old != null ? old - price : 0,
    category: "shoes", emoji: "📦", when: "недавно",
    url: t.url, active: t.is_active,
    near: !!(target && price && price <= target * 1.06),
    history, image_url: t.image_url,
    alert_drop_percent: t.alert_drop_percent, alert_rise_percent: t.alert_rise_percent,
  };
}

// ---------- Art / sparkline ----------
function artHtml(i) {
  if (i.image_url) {
    return `<img src="${escapeHtml(i.image_url)}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">`;
  }
  return `<span style="font-size:34px">${i.emoji}</span>`;
}

function sparkline(vals) {
  vals = (vals && vals.length) ? vals : [0];
  const w = 100, h = 35;
  const min = Math.min(...vals), max = Math.max(...vals), range = (max - min) || 1;
  const pts = vals.map((v, idx) => `${(idx / (vals.length - 1)) * w},${h - 4 - ((v - min) / range) * (h - 10)}`).join(" ");
  const color = vals[vals.length - 1] <= vals[0] ? "#21a464" : "#dd7b5d";
  return `<svg class="mini-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function priceChart(vals, w = 450, h = 140) {
  vals = (vals && vals.length) ? vals.slice() : [0];
  if (vals.length === 1) vals = [vals[0], vals[0]];
  const min = Math.min(...vals), max = Math.max(...vals);
  const flat = max === min;
  const range = flat ? 1 : (max - min);
  const padX = 42, padTop = 12, padBot = 16;
  const iw = w - padX - 8, ih = h - padTop - padBot;
  const yFor = v => flat ? padTop + ih / 2 : padTop + ih - ((v - min) / range) * ih;
  const pts = vals.map((v, idx) => {
    const x = padX + (idx / (vals.length - 1)) * iw;
    return `${x.toFixed(1)},${yFor(v).toFixed(1)}`;
  }).join(" ");
  const area = `M${padX},${padTop + ih} L${pts.replaceAll(",", " ")} L${padX + iw},${padTop + ih} Z`;
  const mid = (min + max) / 2;
  const fmt = v => Math.round(v).toLocaleString("ru-RU");
  return `<svg class="history-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px;margin-top:3px">
    <defs><linearGradient id="hcFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#22a765" stop-opacity=".18"/><stop offset="1" stop-color="#22a765" stop-opacity="0"/></linearGradient></defs>
    <g stroke="#edf1ed" stroke-dasharray="4 5"><path d="M${padX} ${padTop}H${w-8}M${padX} ${padTop+ih/2}H${w-8}M${padX} ${padTop+ih}H${w-8}"/></g>
    <g fill="#9ba69f" font-size="11"><text x="0" y="${padTop+4}">${fmt(max)}</text><text x="0" y="${padTop+ih/2+4}">${fmt(mid)}</text><text x="0" y="${padTop+ih+4}">${fmt(min)}</text></g>
    <path d="${area}" fill="url(#hcFill)"/>
    <polyline points="${pts}" fill="none" stroke="#1eaa66" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

// ---------- Cards / grid / table ----------
function filteredItems(filter = activeFilter, search = "") {
  return items.filter(i => {
    if (filter === "down" && i.change >= 0) return false;
    if (filter === "near" && !i.near) return false;
    if (filter === "paused" && i.active) return false;
    if (search && !(i.name + "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
}

function cardHTML(i) {
  const target = i.target && i.target > 0 ? i.target : i.price;
  const gap = i.price != null ? Math.max(0, i.price - (target || i.price)) : 0;
  const saved = i.price ? Math.max(0, Math.min(100, (i.price - target) / i.price * 100)) : 0;
  return `<article class="product-card" onclick="openDetail(${i.id})" tabindex="0" role="button">
    <div class="product-top">
      <div class="product-art ${i.active ? "" : "paused"}" style="display:grid;place-items:center;overflow:hidden">${artHtml(i)}</div>
      <div class="product-info">
        <div class="market"><span class="market-dot" style="background:${i.active ? "#24a866" : "#b5beb7"}"></span>${escapeHtml(i.market)}</div>
        <h4 class="product-title">${escapeHtml(i.name)}</h4>
        <div class="location">${i.active ? "Отслеживается" : "На паузе"}</div>
      </div>
    </div>
    <div class="price-row"><span class="price">${money(i.price)}</span>${i.old && i.old !== i.price ? `<span class="old-price">${money(i.old)}</span>` : ""}</div>
    <div class="change-badge ${i.change > 0 ? "up" : ""}">${i.change <= 0 ? "↓" : "↑"} ${pct(i.change)} <span style="font-weight:500;opacity:.8">за период</span></div>
    ${sparkline(i.history)}
    <div class="target-row">
      <div><div class="target-label">Твоя целевая цена</div><div class="target-value">${money(target)}</div></div>
      <div style="text-align:right"><div class="target-label">${i.price != null && i.price <= target ? "Цель достигнута" : "До цели " + money(gap)}</div><div class="target-progress" style="width:116px"><span style="width:${100 - saved}%"></span></div></div>
    </div>
    <div class="card-footer">
      <span class="check-time">${icon("clock")} ${i.active ? "Следим за ценой" : "На паузе"}</span>
      <div class="tiny-action">
        <button class="tiny-btn" title="${i.active ? "Пауза" : "Продолжить"}" onclick="event.stopPropagation();togglePause(${i.id})">${icon(i.active ? "pause" : "play")}</button>
        <button class="tiny-btn" title="Удалить" onclick="event.stopPropagation();removeTrack(${i.id})">${icon("trash")}</button>
      </div>
    </div>
  </article>`;
}

function renderGrid() {
  const search = (document.getElementById("globalSearch") || {}).value || "";
  const list = filteredItems(activeFilter, search);
  document.getElementById("productGrid").innerHTML = list.map(cardHTML).join("");
  document.getElementById("overviewEmpty").classList.toggle("hidden", list.length !== 0);
}

function renderTable() {
  const search = ((document.getElementById("tableSearch") || {}).value || "").trim().toLowerCase();
  const filter = (document.getElementById("tableFilter") || {}).value || "all";
  const list = items.filter(i =>
    (!search || (i.name + "").toLowerCase().includes(search)) &&
    (filter === "all" || (filter === "active" && i.active) || (filter === "paused" && !i.active) || (filter === "down" && i.change < 0))
  );
  document.getElementById("tracksTable").innerHTML = list.map(i => `
    <tr>
      <td><div class="table-product"><div class="table-thumb" style="overflow:hidden">${i.image_url ? `<img src="${escapeHtml(i.image_url)}" style="width:100%;height:100%;object-fit:cover">` : i.emoji}</div><div><strong>${escapeHtml(i.name)}</strong><small>${escapeHtml(i.market)}</small></div></div></td>
      <td><strong>${money(i.price)}</strong></td>
      <td style="color:${i.change <= 0 ? "#168653" : "#d36e54"};font-weight:700">${i.change <= 0 ? "↓" : "↑"} ${pct(i.change)}</td>
      <td>${money(i.target)}</td>
      <td><span class="status-pill ${i.active ? "" : "paused"}">${i.active ? "Активно" : "На паузе"}</span></td>
      <td><button class="tiny-btn" onclick="openDetail(${i.id})">${icon("chevron")}</button></td>
    </tr>`).join("") || `<tr><td colspan="6" style="padding:35px;text-align:center;color:#8a978e">Ничего не найдено</td></tr>`;
}

function renderStats() {
  const n = items.length;
  const navCount = document.getElementById("navCount");
  if (navCount) { navCount.textContent = n; navCount.style.display = n > 0 ? "" : "none"; }
  const statTracked = document.getElementById("statTracked");
  if (statTracked) statTracked.textContent = n;
  const filterAll = document.getElementById("filterAllCount");
  if (filterAll) { filterAll.textContent = n; filterAll.style.display = n > 0 ? "" : "none"; }
}

function renderAll() { renderStats(); renderGrid(); renderTable(); renderHistoryAside(); }

function navigate(page, historyId = null) {
  document.querySelectorAll(".page-section").forEach(s => s.classList.remove("active"));
  const target = document.getElementById("page-" + page);
  if (target) target.classList.add("active");
  document.querySelectorAll("[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  const names = { overview: "Обзор", tracks: "Мои отслеживания", history: "История цен", alerts: "Уведомления", settings: "Настройки", help: "Помощь" };
  document.getElementById("topPageTitle").textContent = names[page] || "Ценолов";
  if (page === "tracks") renderTable();
  if (page === "overview") renderGrid();
  if (page === "alerts") loadAlerts();
  if (page === "history") renderHistory(historyId);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- Modals ----------
function openAddModal() {
  document.getElementById("addModal").classList.add("open");
  setTimeout(() => document.getElementById("productUrl").focus(), 40);
}
function closeModal(id) { document.getElementById(id).classList.remove("open"); }
function backdropClose(e, id) { if (e.target.id === id) closeModal(id); }

// ---------- Detail ----------
async function openDetail(id) {
  const i = items.find(x => x.id === id);
  if (!i) { showToast("Товар не найден"); return; }
  currentDetailId = id;

  let hist = i.history || [];
  try { hist = (await api(`/api/tracks/${id}/history`)).map(h => h.price); } catch (e) {}
  if (!hist.length) hist = [i.price];

  document.getElementById("detailName").textContent = i.name;
  document.getElementById("detailSub").textContent = i.market;
  document.getElementById("detailArt").className = "product-art";
  document.getElementById("detailArt").innerHTML = artHtml(i);
  document.getElementById("detailMarket").textContent = i.market;
  document.getElementById("detailPrice").textContent = money(i.price);
  document.getElementById("detailChange").textContent = (i.change <= 0 ? "↓ " : "↑ ") + pct(i.change) + " за период";
  document.getElementById("detailTarget").textContent = money(i.target);
  document.getElementById("detailGap").textContent = (i.price != null && i.target != null && i.price <= i.target) ? "Достигнута" : money(i.target != null && i.price != null ? i.price - i.target : null);
  document.getElementById("detailStatus").textContent = i.active ? "Активно" : "Пауза";
  document.getElementById("detailBadge").textContent = pct(i.change);

  const dTarget = document.getElementById("dTarget");
  if (dTarget) dTarget.value = i.target ?? "";
  const dDrop = document.getElementById("dDrop");
  if (dDrop) dDrop.value = i.alert_drop_percent ?? "";
  const dRise = document.getElementById("dRise");
  if (dRise) dRise.value = i.alert_rise_percent ?? "";

  const pauseBtn = document.getElementById("detailPause");
  if (pauseBtn) pauseBtn.innerHTML = icon(i.active ? "pause" : "play") + (i.active ? " Приостановить" : " Продолжить");

  const chartEl = document.querySelector("#detailModal svg.history-chart");
  if (chartEl) chartEl.outerHTML = priceChart(hist, 450, 140);

  const linkEl = document.getElementById("detailOpenLink");
  if (linkEl) linkEl.onclick = () => { const tg = window.Telegram && window.Telegram.WebApp; if (tg && tg.openLink) tg.openLink(i.url); else window.open(i.url, "_blank"); };

  document.getElementById("detailModal").classList.add("open");
}

function toggleCurrentPause() { if (currentDetailId) togglePause(currentDetailId); }

async function togglePause(id) {
  const i = items.find(x => x.id === id);
  if (!i) return;
  try {
    await api(`/api/tracks/${id}`, { method: "PATCH", body: JSON.stringify({ is_active: !i.active }) });
    i.active = !i.active;
    renderAll();
    if (currentDetailId === id) openDetail(id);
    showToast(i.active ? "Отслеживание возобновлено" : "Отслеживание приостановлено");
  } catch (e) { showToast(e.message); }
}

async function removeTrack(id) {
  if (!confirm("Удалить товар из отслеживания?")) return;
  try {
    await api(`/api/tracks/${id}`, { method: "DELETE" });
    items = items.filter(x => x.id !== id);
    renderAll();
    closeModal("detailModal");
    showToast("Товар удалён");
  } catch (e) { showToast(e.message); }
}

async function saveDetailSettings() {
  if (!currentDetailId) return;
  const body = {
    target_price: document.getElementById("dTarget").value || null,
    alert_drop_percent: document.getElementById("dDrop").value || null,
    alert_rise_percent: document.getElementById("dRise").value || null,
  };
  try {
    await api(`/api/tracks/${currentDetailId}`, { method: "PATCH", body: JSON.stringify(body) });
    await loadAll();
    openDetail(currentDetailId);
    showToast("Условия сохранены 💚");
  } catch (e) { showToast(e.message); }
}

// ---------- Add ----------
async function submitAdd(e) {
  e.preventDefault();
  const url = document.getElementById("productUrl").value.trim();
  if (!url) return;
  const target = document.getElementById("targetPrice").value;
  const threshold = document.getElementById("threshold").value;
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api("/api/tracks", {
      method: "POST",
      body: JSON.stringify({
        url,
        target_price: target ? parseFloat(target) : null,
        alert_drop_percent: threshold === "0" ? null : parseFloat(threshold),
      }),
    });
    closeModal("addModal");
    e.target.reset();
    await loadAll();
    navigate("overview");
    showToast("Товар добавлен! Начинаем наблюдение 💚");
  } catch (err) {
    showToast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ---------- Load ----------
async function loadAll() {
  const [me, tracks, alerts] = await Promise.all([api("/api/me"), api("/api/tracks"), api("/api/alerts")]);
  items = tracks.map(mapTrack);
  renderAll();
  renderSettings(me);
  renderAlertsBadge(me.alerts_count || 0);
  renderOverviewAside(alerts);
}

function setSwitch(key, on) {
  const el = document.querySelector(`[data-notify="${key}"], [data-setting="${key}"]`);
  if (el) el.classList.toggle("on", !!on);
}
function renderSettings(me) {
  setSwitch("drop", me.notify_drop);
  setSwitch("target", me.notify_target);
  setSwitch("rise", me.notify_rise);
  setSwitch("notify_daily_digest", me.notify_daily_digest);
  const freq = document.getElementById("checkFrequency");
  if (freq) freq.value = String(me.check_interval_minutes || 15);
}

// ---------- Misc ----------
async function toggleSwitch(el) {
  const key = el.dataset.notify;
  const setting = el.dataset.setting;
  if (!key && !setting) { el.classList.toggle("on"); return; }
  el.classList.toggle("on");
  const value = el.classList.contains("on");
  const body = key ? { ["notify_" + key]: value } : { [setting]: value };
  try {
    await api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
    showToast("Настройки сохранены");
  } catch (e) {
    el.classList.toggle("on");
    showToast(e.message);
  }
}

function showToast(msg) {
  const t = document.getElementById("toast");
  document.getElementById("toastText").textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2700);
}

// ---------- Alerts ----------
const ALERT_ICONS = { DROP: "arrow-up", RISE: "chart", TARGET: "target", REMOVED: "trash" };
function alertText(a) {
  const o = money(a.old_price), n = money(a.new_price);
  switch (a.alert_type) {
    case "DROP": return `Цена снизилась на <b>${o} → ${n}</b>`;
    case "RISE": return `Цена выросла до <b>${n}</b>`;
    case "TARGET": return `Достигнута целевая цена <b>${n}</b>`;
    case "REMOVED": return `Объявление снято с продажи`;
    default: return "Изменение цены";
  }
}
function alertTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
async function markAllRead() {
  try {
    await api("/api/alerts/read-all", { method: "POST" });
    renderAlertsBadge(0);
    await loadAlerts();
    showToast("Уведомления очищены");
  } catch (e) { showToast(e.message); }
}

async function loadAlerts() {
  try {
    const list = await api("/api/alerts");
    const box = document.getElementById("alertsList");
    if (!box) return;
    if (!list.length) {
      box.innerHTML = '<div class="empty">Пока нет уведомлений.<br/>Они появятся, когда цена изменится.</div>';
      return;
    }
    box.innerHTML = list.map(a => `
      <section class="panel" style="margin-top:14px"><div class="alert-item">
        <div class="alert-avatar">${icon(ALERT_ICONS[a.alert_type] || "bell")}</div>
        <div class="alert-copy"><strong>${escapeHtml(a.title)}</strong><p>${alertText(a)}</p></div>
        <span class="alert-time">${alertTime(a.sent_at)}</span>
      </div></section>`).join("");
  } catch (e) { /* ignore */ }
}

// ---------- History ----------
function renderHistoryAside() {
  const avgEl = document.getElementById("historyAvgChange");
  if (avgEl) {
    const active = items.filter(i => i.active);
    const changes = active.map(i => i.change).filter(x => x != null);
    const avg = changes.length ? changes.reduce((a, b) => a + b, 0) / changes.length : null;
    avgEl.textContent = avg == null ? "—" : pct(avg);
  }
}

function renderHistory(preferredId = null) {
  renderHistoryAside();
  const sel = document.getElementById("historyProduct");
  if (!sel) return;
  sel.innerHTML = items.map(i => `<option value="${i.id}">${escapeHtml(i.name)}</option>`).join("");
  const targetId = preferredId != null ? preferredId : (items[0] ? items[0].id : null);
  const period = document.getElementById("historyPeriod");
  const days = period ? Number(period.value) : 7;
  if (targetId != null) {
    sel.value = String(targetId);
    showHistoryChart(Number(targetId), days);
  } else if (document.getElementById("historyBig")) {
    document.getElementById("historyBig").textContent = "—";
  }
}

async function showHistoryChart(id, days = 7) {
  const i = items.find(x => x.id === id);
  if (!i) return;
  let rows = [];
  try { rows = await api(`/api/tracks/${id}/history?days=${days}`); } catch (e) {}
  let hist = rows.map(r => r.price);
  if (!hist.length) hist = (i.history && i.history.length) ? i.history : [i.price];
  const first = hist[0], last = hist[hist.length - 1];
  const change = first ? ((last - first) / first) * 100 : 0;
  const big = document.getElementById("historyBig");
  if (big) big.textContent = pct(change);
  renderHistoryTicks(rows);
  const el = document.querySelector("#page-history svg.history-chart");
  if (el) el.outerHTML = priceChart(hist, 700, 280);
}

function renderHistoryTicks(rows) {
  const el = document.getElementById("historyTicks");
  if (!el) return;
  if (!rows || rows.length === 0) { el.innerHTML = ""; return; }
  const fmt = ts => {
    const d = new Date(ts);
    return isNaN(d) ? "" : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  };
  const n = rows.length;
  const idxs = [...new Set([0, Math.floor((n - 1) / 3), Math.floor((2 * (n - 1)) / 3), n - 1])];
  el.innerHTML = idxs.map(idx => `<span>${fmt(rows[idx].timestamp)}</span>`).join("");
}

// ---------- Overview aside (динамика + последние события) ----------
function aggregateSeries(tracks) {
  const series = tracks
    .filter(t => t.history && t.history.length >= 2)
    .map(t => {
      const base = t.history[0] || 1;
      return t.history.map(v => (base ? (v / base) * 100 : 100));
    });
  if (!series.length) return null;
  const len = Math.min(...series.map(s => s.length));
  const avg = [];
  for (let i = 0; i < len; i++) {
    avg.push(series.reduce((sum, s) => sum + s[i], 0) / series.length);
  }
  return avg;
}

function renderOverviewAside(alerts) {
  const active = items.filter(i => i.active);
  const changes = active.map(i => i.change).filter(x => x != null);
  const avg = changes.length ? changes.reduce((a, b) => a + b, 0) / changes.length : null;

  const dynBig = document.getElementById("dynBig");
  const dynSmall = document.getElementById("dynSmall");
  if (dynBig) dynBig.textContent = avg == null ? "—" : pct(avg);
  if (dynSmall) dynSmall.textContent = avg == null ? "" : (avg < 0 ? "↓ дешевле" : avg > 0 ? "↑ дороже" : "→ без изменений");

  const summary = document.querySelector(".summary-chart");
  if (summary) {
    const series = aggregateSeries(active);
    if (series) summary.outerHTML = priceChart(series, 270, 135);
  }

  // статистика обзора
  const nearCount = active.filter(i => i.near).length;
  const statNear = document.getElementById("statNear");
  if (statNear) statNear.textContent = nearCount;
  const statAvg = document.getElementById("statAvgChange");
  if (statAvg) statAvg.textContent = avg == null ? "—" : pct(avg);
  const statAlerts = document.getElementById("statAlerts");
  if (statAlerts) statAlerts.textContent = (alerts || []).length;

  // цель на месяц (потенциальная экономия)
  let savings = 0;
  for (const i of active) {
    if (i.target && i.price != null && i.price > i.target) savings += i.price - i.target;
  }
  const goalAmount = document.getElementById("goalAmount");
  if (goalAmount) goalAmount.textContent = money(savings);
  const goalProgress = document.getElementById("goalProgress");
  const goalPct = active.length ? Math.round((nearCount / active.length) * 100) : 0;
  if (goalProgress) goalProgress.style.width = goalPct + "%";
  const goalNote = document.getElementById("goalNote");
  if (goalNote) goalNote.textContent = active.length
    ? `${nearCount} из ${active.length} товаров близки к цели.`
    : "Добавьте товары, чтобы видеть экономию.";

  const activeIds = new Set(active.map(i => i.id));
  const recent = (alerts || []).filter(a => activeIds.has(a.track_id)).slice(0, 3);
  const box = document.getElementById("recentEvents");
  if (box) {
    box.innerHTML = recent.length
      ? recent.map(a => `<div class="alert-item"><div class="alert-avatar">${icon(ALERT_ICONS[a.alert_type] || "bell")}</div><div class="alert-copy"><strong>${escapeHtml(a.title)}</strong><p>${alertText(a)}</p></div><span class="alert-time">${alertTime(a.sent_at)}</span></div>`).join("")
      : '<div class="empty" style="padding:20px 0">Пока нет событий.</div>';
  }
}

// ---------- Alerts badge + history navigation ----------
function renderAlertsBadge(n) {
  const el = document.getElementById("alertsCount");
  if (!el) return;
  el.textContent = n;
  el.style.display = n > 0 ? "" : "none";
}

function openHistoryFor(id) {
  closeModal("detailModal");
  navigate("history", id);
}

// ---------- Init ----------
(function init() {
  // Telegram WebApp
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor("#f5f7f5");
      if (tg.setBackgroundColor) tg.setBackgroundColor("#f5f7f5");
      const user = tg.initDataUnsafe && tg.initDataUnsafe.user;
      if (user && user.first_name) {
        document.querySelectorAll(".profile-name").forEach(el => el.textContent = user.first_name);
        const av = document.querySelector(".profile .avatar");
        if (av) av.textContent = (user.first_name[0] || "P").toUpperCase();
        const topAv = document.querySelector(".profile-top");
        if (topAv) topAv.textContent = (user.first_name[0] || "P").toUpperCase();
      }
    }
  } catch (e) {}

  // дата
  try {
    const d = new Date();
    document.getElementById("currentDate").textContent = new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long" }).format(d).toUpperCase("ru-RU");
  } catch (e) {}

  // навигация
  document.querySelectorAll("[data-page]").forEach(b => b.addEventListener("click", () => navigate(b.dataset.page)));
  document.querySelectorAll("#overviewFilters [data-filter]").forEach(b => b.addEventListener("click", () => {
    activeFilter = b.dataset.filter;
    document.querySelectorAll("#overviewFilters [data-filter]").forEach(x => x.classList.toggle("active", x === b));
    renderGrid();
  }));
  const gs = document.getElementById("globalSearch");
  if (gs) gs.addEventListener("input", () => { if (!document.getElementById("page-overview").classList.contains("active")) navigate("overview"); renderGrid(); });
  const ts = document.getElementById("tableSearch");
  if (ts) ts.addEventListener("input", renderTable);
  const tf = document.getElementById("tableFilter");
  if (tf) tf.addEventListener("change", renderTable);

  // add form
  const form = document.getElementById("addForm");
  if (form) form.addEventListener("submit", submitAdd);
  const freq = document.getElementById("checkFrequency");
  if (freq) freq.addEventListener("change", async () => {
    try {
      await api("/api/settings", { method: "PATCH", body: JSON.stringify({ check_interval_minutes: Number(freq.value) }) });
      showToast("Частота проверок обновлена");
    } catch (e) { showToast(e.message); }
  });

  // Esc
  document.addEventListener("keydown", e => { if (e.key === "Escape") document.querySelectorAll(".modal-backdrop.open").forEach(m => m.classList.remove("open")); });

  // инжектируем кнопки в карточку товара
  const pauseBtn = document.getElementById("detailPause");
  if (pauseBtn && !document.getElementById("btnDelete")) {
    const del = document.createElement("button");
    del.className = "btn btn-light"; del.id = "btnDelete";
    del.style.marginLeft = "8px";
    del.innerHTML = icon("trash") + " Удалить";
    del.onclick = () => removeTrack(currentDetailId);
    pauseBtn.insertAdjacentElement("afterend", del);
  }
  const dSave = document.getElementById("dSave");
  if (dSave) dSave.addEventListener("click", saveDetailSettings);
  const historySel = document.getElementById("historyProduct");
  if (historySel) historySel.addEventListener("change", () => showHistoryChart(Number(historySel.value)));
  const historyPeriod = document.getElementById("historyPeriod");
  if (historyPeriod) historyPeriod.addEventListener("change", () => {
    const sel = document.getElementById("historyProduct");
    const id = sel && sel.value ? Number(sel.value) : (items[0] ? items[0].id : null);
    if (id != null) showHistoryChart(id, Number(historyPeriod.value));
  });

  // загрузка данных
  loadAll().catch(e => showToast(e.message));
})();
