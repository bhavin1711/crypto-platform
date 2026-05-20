
// ── Configuration ─────────────────────────────────────────────────────────────
// In production: set window.API_BASE to your Azure App Service URL before
// this script runs (e.g. via a <script>window.API_BASE = "https://..."</script>
// injected at deploy time, or via Azure Static Web Apps environment variables).
const API_BASE = window.API_BASE || "http://localhost:8000";

// ── Application state ─────────────────────────────────────────────────────────
const state = {
  scanTf:      "4h",
  scanFilter:  "all",
  scanResults: [],

  chartSym: "BTCUSDT",
  chartTf:  "4h",

  btTf: "4h",
};

let priceChart = null;   // Chart.js instance — destroyed and rebuilt on each load


// ═══════════════════════════════════════════════════════════════════════════════
// TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════

function switchTab(tab) {
  ["scanner", "chart", "backtest"].forEach(t => {
    document.getElementById(`view-${t}`).classList.toggle("hidden", t !== tab);
    document.getElementById(`tab-${t}`).classList.toggle("active", t === tab);
  });
}


// ═══════════════════════════════════════════════════════════════════════════════
// SCANNER
// ═══════════════════════════════════════════════════════════════════════════════

async function loadScan(force = false) {
  showEl("scan-loading");
  hideEl("global-error");

  try {
    const data = await apiFetch(`/scan?interval=${state.scanTf}`);
    state.scanResults = data.results || [];
    renderScanResults();
    renderScanInsight();
  } catch (e) {
    showError(e.message);
  } finally {
    hideEl("scan-loading");
  }
}

function renderScanResults() {
  const search = document.getElementById("scan-search").value.toUpperCase();
  let rows = state.scanResults;
  if (state.scanFilter === "buy")  rows = rows.filter(r => r.signal?.signal === "BUY");
  if (state.scanFilter === "sell") rows = rows.filter(r => r.signal?.signal === "SELL");
  if (search) rows = rows.filter(r => r.base?.includes(search) || r.symbol?.includes(search));

  // Summary bar
  const counts = { BUY: 0, HOLD: 0, SELL: 0 };
  state.scanResults.forEach(r => { counts[r.signal?.signal ?? "HOLD"]++; });
  document.getElementById("scan-summary").innerHTML = `
    <div class="sum-card"><div class="v" style="color:var(--green)">${counts.BUY}</div><div class="label">Buy</div></div>
    <div class="sum-card"><div class="v" style="color:var(--yellow)">${counts.HOLD}</div><div class="label">Hold</div></div>
    <div class="sum-card"><div class="v" style="color:var(--red)">${counts.SELL}</div><div class="label">Sell</div></div>
    <div class="sum-card"><div class="v">${state.scanResults.length}</div><div class="label">Scanned</div></div>
    <div class="sum-card"><div class="v" style="font-size:13px">${new Date().toLocaleTimeString()}</div><div class="label">Updated</div></div>
  `;

  // Table rows
  const body = document.getElementById("scan-body");
  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:20px">No matching results.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(r => {
    const sig = r.signal?.signal ?? "HOLD";
    const cls = sig.toLowerCase();
    const chgCls = r.changePct >= 0 ? "up" : "down";
    return `
      <tr class="clickable" onclick="openChart('${r.symbol}')">
        <td><strong>${r.base}</strong> <span class="small-text">${r.symbol}</span></td>
        <td><span class="pill ${cls}">${sig}</span></td>
        <td class="num">${fmtPrice(r.lastPrice)}</td>
        <td class="num ${chgCls}">${r.changePct >= 0 ? "+" : ""}${r.changePct.toFixed(2)}%</td>
        <td class="hide-mobile small-text">${r.signal?.reason ?? "—"}</td>
        <td class="num hide-mobile">${fmtVol(r.volume)}</td>
      </tr>
    `;
  }).join("");
}

async function renderScanInsight() {
  // Build a simple market breadth narrative client-side using the scan results.
  // (The full insight engine lives server-side; this is a lightweight summary.)
  const counts = { BUY: 0, HOLD: 0, SELL: 0 };
  state.scanResults.forEach(r => { counts[r.signal?.signal ?? "HOLD"]++; });
  const total   = state.scanResults.length;
  const leaders = state.scanResults.filter(r => r.signal?.signal === "BUY").slice(0, 4).map(r => r.base);
  const laggards = state.scanResults.filter(r => r.signal?.signal === "SELL").slice(0, 4).map(r => r.base);

  const breadth = counts.BUY / Math.max(counts.SELL, 1);
  let regime, cls, context;
  if (breadth >= 2)       { regime = "broadly constructive"; cls = "pos"; context = "A strong majority of markets show uptrend alignment — broad-based momentum."; }
  else if (breadth >= 1)  { regime = "cautiously constructive"; cls = "pos"; context = "More markets trend up than down, but conviction is not yet decisive."; }
  else if (breadth < 0.5) { regime = "broadly defensive"; cls = "neg"; context = "A majority of markets show downtrend alignment — risk-off conditions."; }
  else                    { regime = "mixed / range-bound"; cls = "neutral"; context = "No dominant directional bias — patience and selectivity are appropriate."; }

  const html = [
    `<p><strong>Market regime:</strong> Across ${total} markets scanned, breadth reads <span class="${cls}">${regime}</span>. ${context}</p>`,
    `<p><strong>Distribution:</strong> ${counts.BUY} BUY · ${counts.HOLD} HOLD · ${counts.SELL} SELL.</p>`,
    leaders.length  ? `<p><strong>Leaders:</strong> <span class="pos">${leaders.join(", ")}</span> — Price &gt; SMA20 &gt; SMA50.</p>` : "",
    laggards.length ? `<p><strong>Laggards:</strong> <span class="neg">${laggards.join(", ")}</span> — Price &lt; SMA20 &lt; SMA50.</p>` : "",
    `<p class="small-text"><em>Rule-based NLG · LLM-swappable without changing frontend logic</em></p>`,
  ].filter(Boolean).join("");

  document.getElementById("scan-insight").innerHTML = html;
  document.getElementById("scan-insight-meta").textContent =
    `Generated ${new Date().toLocaleTimeString()} · rule-based NLG`;
}

// Open chart tab for a symbol clicked in the scanner
function openChart(symbol) {
  state.chartSym = symbol;
  document.getElementById("chart-sym-input").value = symbol.replace("USDT", "");
  switchTab("chart");
  loadChart();
}


// ═══════════════════════════════════════════════════════════════════════════════
// CHART VIEW
// ═══════════════════════════════════════════════════════════════════════════════

async function loadChart() {
  showEl("chart-loading");
  hideEl("global-error");

  try {
    // Two parallel API calls: signal (candles + SMA series) and insight (narrative)
    const [sigData, insightData] = await Promise.all([
      apiFetch(`/signal/${state.chartSym}?interval=${state.chartTf}`),
      apiFetch(`/insight/${state.chartSym}?interval=${state.chartTf}`),
    ]);

    renderSignalPanel(sigData);
    renderPriceChart(sigData);
    renderInsightPanel(insightData);
  } catch (e) {
    showError(e.message);
  } finally {
    hideEl("chart-loading");
  }
}

function renderSignalPanel(data) {
  const sig   = data.signal;
  const base  = data.symbol.replace("USDT", "");
  const price = sig.price;

  // Price row (use last close from series as the "current" price)
  const priceEl = document.getElementById("chart-price");
  priceEl.textContent = fmtPrice(price);
  document.getElementById("chart-header").textContent =
    `${base}/USDT · ${data.interval} timeframe · ${data.series.closes.length} candles`;
  document.getElementById("chart-price-row").style.display = "flex";

  // Signal banner
  const banner = document.getElementById("chart-signal-banner");
  banner.className = `signal-banner ${sig.signal.toLowerCase()}`;
  banner.innerHTML = `${sig.signal}<div class="signal-conf">${sig.reason}</div>`;

  // Indicator tiles
  document.getElementById("chart-indicators").innerHTML = `
    <div class="indicator"><div class="label">Price</div><div class="v">${fmtPrice(sig.price)}</div></div>
    <div class="indicator"><div class="label">SMA 20</div><div class="v">${fmtPrice(sig.sma20)}</div></div>
    <div class="indicator"><div class="label">SMA 50</div><div class="v">${fmtPrice(sig.sma50)}</div></div>
    <div class="indicator"><div class="label">Signal</div><div class="v">${sig.signal}</div></div>
  `;
}

function renderPriceChart(data) {
  const { closes, sma20, sma50, timestamps } = data.series;
  const tf = data.interval;

  const labels = timestamps.map(t => {
    const d = new Date(t);
    return tf === "1d"
      ? `${d.getMonth() + 1}/${d.getDate()}`
      : `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:00`;
  });

  if (priceChart) priceChart.destroy();
  priceChart = new Chart(document.getElementById("price-chart").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Close",  data: closes, borderColor: "#58a6ff", borderWidth: 2, pointRadius: 0, tension: 0.1 },
        { label: "SMA 20", data: sma20,  borderColor: "#d29922", borderWidth: 1.5, pointRadius: 0, borderDash: [4, 3] },
        { label: "SMA 50", data: sma50,  borderColor: "#7c3aed", borderWidth: 1.5, pointRadius: 0, borderDash: [4, 3] },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: true, labels: { color: "#8b949e", boxWidth: 14 } },
        tooltip: { backgroundColor: "#161b22", borderColor: "#2a3140", borderWidth: 1 },
      },
      scales: {
        x: { ticks: { color: "#8b949e", maxTicksLimit: 8 }, grid: { color: "rgba(255,255,255,0.04)" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "rgba(255,255,255,0.04)" } },
      },
    },
  });
}

function renderInsightPanel(data) {
  document.getElementById("chart-insight").innerHTML = data.narrative;
  document.getElementById("chart-insight-meta").textContent =
    `Generated ${new Date().toLocaleTimeString()} · rule-based NLG`;
}

function setChartSym(base) {
  const sym = base.toUpperCase() + "USDT";
  state.chartSym = sym;
  document.getElementById("chart-sym-input").value = base;
  loadChart();
}

function loadChartForInput() {
  const val = document.getElementById("chart-sym-input").value.trim().toUpperCase();
  if (!val) return;
  state.chartSym = val.endsWith("USDT") ? val : val + "USDT";
  loadChart();
}


// ═══════════════════════════════════════════════════════════════════════════════
// BACKTEST
// ═══════════════════════════════════════════════════════════════════════════════

async function loadBacktest() {
  const sym = document.getElementById("bt-sym").value.trim().toUpperCase() || "BTC";
  showEl("bt-loading");
  hideEl("bt-results");
  hideEl("bt-error");

  try {
    const data = await apiFetch(`/backtest/${sym}?interval=${state.btTf}`);
    renderBacktest(data);
    showEl("bt-results");
  } catch (e) {
    document.getElementById("bt-error").textContent = e.message;
    showEl("bt-error");
  } finally {
    hideEl("bt-loading");
  }
}

function renderBacktest(data) {
  const pnl    = (data.final_portfolio - 100).toFixed(2);
  const bhPnl  = (data.buy_and_hold - 100).toFixed(2);
  const won    = data.outperformed;

  const verdict = document.getElementById("bt-verdict");
  verdict.className = `signal-banner ${won ? "buy" : "sell"}`;
  verdict.innerHTML = `
    ${won ? "Outperformed" : "Underperformed"} Buy &amp; Hold
    <div class="signal-conf">
      Strategy: $${data.final_portfolio} · Buy &amp; Hold: $${data.buy_and_hold}
    </div>
  `;

  document.getElementById("bt-stats").innerHTML = `
    <div class="stat-card"><div class="label">Strategy P/L</div>
      <div class="v ${pnl >= 0 ? "up" : "down"}">${pnl >= 0 ? "+" : ""}$${pnl}</div></div>
    <div class="stat-card"><div class="label">Buy &amp; Hold P/L</div>
      <div class="v ${bhPnl >= 0 ? "up" : "down"}">${bhPnl >= 0 ? "+" : ""}$${bhPnl}</div></div>
    <div class="stat-card"><div class="label">Total Trades</div><div class="v">${data.total_trades}</div></div>
    <div class="stat-card"><div class="label">Win Rate</div><div class="v">${data.win_rate != null ? data.win_rate + "%" : "—"}</div></div>
  `;

  document.getElementById("bt-trades").innerHTML = data.trades.length === 0
    ? `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:20px">No trades triggered.</td></tr>`
    : data.trades.map((t, i) => `
        <tr>
          <td>${i + 1}</td>
          <td class="${t.type === "BUY" ? "up" : "down"}">${t.type}</td>
          <td class="num">${fmtPrice(t.price)}</td>
          <td class="num">${fmtPrice(t.sma20)}</td>
          <td class="num">${fmtPrice(t.sma50)}</td>
          <td class="num">$${t.portfolio.toFixed(2)}</td>
        </tr>
      `).join("");
}

function setBtSym(sym) {
  document.getElementById("bt-sym").value = sym;
}


// ═══════════════════════════════════════════════════════════════════════════════
// API CLIENT
// ═══════════════════════════════════════════════════════════════════════════════

async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}


// ═══════════════════════════════════════════════════════════════════════════════
// FORMATTERS
// ═══════════════════════════════════════════════════════════════════════════════

function fmtPrice(v) {
  if (v == null) return "—";
  if (v >= 1000) return "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (v >= 1)    return "$" + v.toFixed(4);
  return "$" + v.toFixed(6);
}

function fmtVol(v) {
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + (v / 1e3).toFixed(1) + "K";
}


// ═══════════════════════════════════════════════════════════════════════════════
// DOM UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════

function showEl(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hideEl(id) { document.getElementById(id)?.classList.add("hidden"); }
function showError(msg) {
  const el = document.getElementById("global-error");
  el.textContent = msg + " — Check that the backend is running on " + API_BASE;
  el.classList.remove("hidden");
}


// ═══════════════════════════════════════════════════════════════════════════════
// EVENT WIRING
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {

  // Scanner timeframe buttons
  document.querySelectorAll(".scan-tf").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".scan-tf").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.scanTf = btn.dataset.tf;
      loadScan();
    });
  });

  // Scanner filter buttons
  document.querySelectorAll(".scan-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".scan-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.scanFilter = btn.dataset.f;
      renderScanResults();
    });
  });

  // Chart timeframe buttons
  document.querySelectorAll(".chart-tf").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chart-tf").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.chartTf = btn.dataset.tf;
      loadChart();
    });
  });

  // Backtest timeframe buttons
  document.querySelectorAll(".bt-tf").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".bt-tf").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.btTf = btn.dataset.tf;
    });
  });

  // Chart symbol input — Enter key
  document.getElementById("chart-sym-input").addEventListener("keydown", e => {
    if (e.key === "Enter") loadChartForInput();
  });

  // Initial load — start on the scanner tab
  // Fix scanner timeframe button init (the HTML has both "1h" and "4h" marked active by mistake)
  document.querySelectorAll(".scan-tf").forEach(b => b.classList.remove("active"));
  document.querySelector('.scan-tf[data-tf="4h"]').classList.add("active");

  loadScan();
});
