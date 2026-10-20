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

function lineChart(vals, w = 450, h = 140) {
  vals = (vals && vals.length > 1) ? vals : [0, 0];
  const min = Math.min(...vals), max = Math.max(...vals), range = (max - min) || 1;
  const pad = 8;
  const pts = vals.map((v, idx) => {
    const x = pad + (idx / (vals.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const area = `M${pad},${h - pad} L${pts.replaceAll(",", " ")} L${w - pad},${h - pad} Z`;
  return `<svg class="history-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:140px;margin-top:3px">
    <defs><linearGradient id="mtFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#22a765" stop-opacity=".18"/><stop offset="1" stop-color="#22a765" stop-opacity="0"/></linearGradient></defs>
    <g stroke="#edf1ed" stroke-dasharray="3 4"><path d="M0 ${h/4}H${w}M0 ${h/2}H${w}M0 ${h*3/4}H${w}"/></g>
    <path d="${area}" fill="url(#mtFill)"/>
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
  document.getElementById("navCount").textContent = n;
  document.getElementById("statTracked").textContent = n;
  document.getElementById("filterAllCount").textContent = n;
}

function renderAll() { renderStats(); renderGrid(); renderTable(); }

function navigate(page) {
  document.querySelectorAll(".page-section").forEach(s => s.classList.remove("active"));
  const target = document.getElementById("page-" + page);
  if (target) target.classList.add("active");
  document.querySelectorAll("[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  const names = { overview: "Обзор", tracks: "Мои отслеживания", history: "История цен", alerts: "Уведомления", settings: "Настройки", help: "Помощь" };
  document.getElementById("topPageTitle").textContent = names[page] || "Ценолов";
  if (page === "tracks") renderTable();
  if (page === "overview") renderGrid();
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

  const pauseBtn = document.getElementById("detailPause");
  if (pauseBtn) pauseBtn.innerHTML = icon(i.active ? "pause" : "play") + (i.active ? " Приостановить" : " Продолжить");

  const chartEl = document.querySelector("#detailModal svg.history-chart");
  if (chartEl) chartEl.outerHTML = lineChart(hist);

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

async function editTarget() {
  if (!currentDetailId) return;
  const i = items.find(x => x.id === currentDetailId);
  if (!i) return;
  const v = prompt("Целевая цена, ₽ (0 — отключить):", i.target || "");
  if (v == null) return;
  try {
    await api(`/api/tracks/${currentDetailId}`, { method: "PATCH", body: JSON.stringify({ target_price: parseFloat(v) || null }) });
    await loadAll();
    openDetail(currentDetailId);
    showToast("Целевая цена обновлена");
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
  const [me, tracks] = await Promise.all([api("/api/me"), api("/api/tracks")]);
  items = tracks.map(mapTrack);
  const count = document.getElementById("statTracked");
  renderAll();
}

// ---------- Misc ----------
function toggleSwitch(el) { el.classList.toggle("on"); }

function showToast(msg) {
  const t = document.getElementById("toast");
  document.getElementById("toastText").textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2700);
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

  // Esc
  document.addEventListener("keydown", e => { if (e.key === "Escape") document.querySelectorAll(".modal-backdrop.open").forEach(m => m.classList.remove("open")); });

  // инжектируем кнопки в карточку товара
  const pauseBtn = document.getElementById("detailPause");
  if (pauseBtn) {
    const row = pauseBtn.parentElement;
    if (row && !document.getElementById("btnEditTarget")) {
      const edit = document.createElement("button");
      edit.className = "btn btn-light"; edit.id = "btnEditTarget";
      edit.style.marginLeft = "8px";
      edit.innerHTML = icon("target") + " Цель";
      edit.onclick = editTarget;
      const del = document.createElement("button");
      del.className = "btn btn-light"; del.style.marginLeft = "8px";
      del.innerHTML = icon("trash") + " Удалить";
      del.onclick = () => removeTrack(currentDetailId);
      row.insertAdjacentElement("afterend", edit);
      edit.insertAdjacentElement("afterend", del);
    }
  }

  // загрузка данных
  loadAll().catch(e => showToast(e.message));
})();
