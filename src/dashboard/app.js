// Dashboard app — fetches JSON from S3, renders charts and tables

const DATA_BASE = 'data/';
const REFRESH_MS = {
  'portfolio-pnl': 30000,
  'movers': 30000,
  'congress': 600000,
  'flow': 60000,
  'darkpool': 120000,
  'technicals': 60000,
};

// ── Tab Navigation ──────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.remove('hidden');
  });
});

// ── Data Fetching ───────────────────────────────────────────────────────

async function fetchData(file) {
  try {
    const resp = await fetch(`${DATA_BASE}${file}?t=${Date.now()}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

// ── Portfolio ───────────────────────────────────────────────────────────

async function loadPortfolio() {
  const data = await fetchData('portfolio-pnl.json');
  if (!data) return;

  const { positions, totals } = data;
  document.getElementById('total-value').textContent = `$${totals.total_value.toLocaleString()}`;
  const pnlEl = document.getElementById('total-pnl');
  pnlEl.textContent = `$${totals.total_dollar_pnl >= 0 ? '+' : ''}${totals.total_dollar_pnl.toLocaleString()} (${totals.total_pct_pnl >= 0 ? '+' : ''}${totals.total_pct_pnl.toFixed(1)}%)`;
  pnlEl.className = `text-2xl font-bold mt-1 ${totals.total_dollar_pnl >= 0 ? 'positive' : 'negative'}`;

  const tbody = document.querySelector('#pnl-table tbody');
  tbody.innerHTML = positions.map(p => `
    <tr>
      <td class="font-semibold">${p.ticker}</td>
      <td>${p.shares}</td>
      <td>$${p.cost_basis.toFixed(2)}</td>
      <td>$${p.current_price.toFixed(2)}</td>
      <td class="${p.dollar_pnl >= 0 ? 'positive' : 'negative'}">$${p.dollar_pnl >= 0 ? '+' : ''}${p.dollar_pnl.toLocaleString()}</td>
      <td class="${p.pct_pnl >= 0 ? 'positive' : 'negative'}">${p.pct_pnl >= 0 ? '+' : ''}${p.pct_pnl.toFixed(1)}%</td>
    </tr>
  `).join('');

  document.getElementById('last-updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

async function loadMovers() {
  const data = await fetchData('movers.json');
  if (!data || !data.movers) return;
  const el = document.getElementById('movers-list');
  el.innerHTML = data.movers.map(m =>
    `<span class="${m.change_pct >= 0 ? 'positive' : 'negative'} mr-4">${m.ticker} ${m.change_pct >= 0 ? '+' : ''}${m.change_pct.toFixed(1)}%</span>`
  ).join('');
}

// ── Congress ────────────────────────────────────────────────────────────

let sectorChart = null;

async function loadCongress() {
  const data = await fetchData('congress.json');
  if (!data) return;

  // Clusters
  const clustersEl = document.getElementById('clusters-list');
  if (data.clusters && data.clusters.length) {
    clustersEl.innerHTML = data.clusters.map(c =>
      `<div class="mb-2 p-2 bg-gray-800 rounded">
        <span class="font-bold text-yellow-400">${c.ticker}</span>: ${c.members.length} members ${c.direction}
        <div class="text-xs text-gray-400">${c.members.slice(0, 3).join(', ')}${c.members.length > 3 ? ` +${c.members.length - 3}` : ''}</div>
      </div>`
    ).join('');
  } else {
    clustersEl.innerHTML = '<div class="text-gray-500">No clusters detected.</div>';
  }

  // Sector chart
  if (data.sectors) {
    const labels = Object.keys(data.sectors);
    const values = Object.values(data.sectors);
    const ctx = document.getElementById('sector-chart').getContext('2d');
    if (sectorChart) sectorChart.destroy();
    sectorChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: ['#3b82f6','#ef4444','#22c55e','#f59e0b','#8b5cf6','#ec4899','#6366f1','#14b8a6'] }],
      },
      options: { responsive: true, plugins: { legend: { position: 'right', labels: { color: '#9ca3af', font: { size: 11 } } } } },
    });
  }

  // Trades table
  const tbody = document.querySelector('#congress-table tbody');
  const trades = data.recent_trades || [];
  tbody.innerHTML = trades.slice(0, 30).map(t => `
    <tr>
      <td>${t.trade_date || ''}</td>
      <td>${t.member || ''}</td>
      <td>${t.party || ''}</td>
      <td class="font-semibold">${t.ticker || ''}</td>
      <td class="${t.tx_type?.includes('Purchase') ? 'positive' : 'negative'}">${t.tx_type || ''}</td>
      <td>${t.amount || ''}</td>
    </tr>
  `).join('');
}

// ── Options Flow ────────────────────────────────────────────────────────

async function loadFlow() {
  const data = await fetchData('flow.json');
  if (!data || !data.tickers) return;
  const tbody = document.querySelector('#flow-table tbody');
  const rows = [];
  data.tickers.forEach(t => {
    (t.top_alerts || []).forEach(a => {
      rows.push(`
        <tr>
          <td class="font-semibold">${a.ticker}</td>
          <td>$${a.strike.toFixed(0)}</td>
          <td>${a.expiry}</td>
          <td>${a.option_type}</td>
          <td>${a.volume.toLocaleString()}</td>
          <td>${a.open_interest.toLocaleString()}</td>
          <td class="${a.volume_oi_ratio >= 10 ? 'text-yellow-400 font-bold' : ''}">${a.volume_oi_ratio.toFixed(1)}x</td>
          <td>$${a.premium.toLocaleString()}</td>
          <td class="${a.direction === 'bullish' ? 'positive' : 'negative'}">${a.direction}</td>
        </tr>
      `);
    });
  });
  tbody.innerHTML = rows.join('');
}

// ── Dark Pool ───────────────────────────────────────────────────────────

async function loadDarkpool() {
  const data = await fetchData('darkpool.json');
  if (!data || !data.tickers) return;
  const tbody = document.querySelector('#darkpool-table tbody');
  tbody.innerHTML = data.tickers.map(t => `
    <tr>
      <td class="font-semibold">${t.ticker}</td>
      <td class="${t.latest_dark_pct > 40 ? 'text-yellow-400 font-bold' : ''}">${t.latest_dark_pct.toFixed(1)}%</td>
      <td class="${t.latest_short_pct > 50 ? 'negative font-bold' : ''}">${t.latest_short_pct.toFixed(1)}%</td>
      <td>${t.trend}</td>
      <td>${t.history?.[0]?.date || ''}</td>
    </tr>
  `).join('');
}

// ── Technicals ──────────────────────────────────────────────────────────

async function loadTechnicals() {
  const data = await fetchData('technicals.json');
  if (!data || !data.tickers) return;
  const tbody = document.querySelector('#technicals-table tbody');
  tbody.innerHTML = data.tickers.map(t => `
    <tr>
      <td class="font-semibold">${t.ticker}</td>
      <td>$${t.price.toFixed(2)}</td>
      <td class="${t.rsi_14 < 30 ? 'negative' : t.rsi_14 > 70 ? 'positive' : ''}">${t.rsi_14.toFixed(1)}</td>
      <td class="${t.macd_histogram > 0 ? 'positive' : 'negative'}">${t.macd_histogram > 0 ? '+' : ''}${t.macd_histogram.toFixed(2)}</td>
      <td class="${t.price > t.sma_50 ? 'positive' : 'negative'}">$${t.sma_50.toFixed(2)}</td>
      <td class="${t.price > t.sma_200 ? 'positive' : 'negative'}">$${t.sma_200.toFixed(2)}</td>
      <td class="font-bold ${t.overall_signal === 'bullish' ? 'positive' : t.overall_signal === 'bearish' ? 'negative' : 'text-gray-400'}">${t.overall_signal.toUpperCase()}</td>
    </tr>
  `).join('');
}

// ── Polling ─────────────────────────────────────────────────────────────

function startPolling() {
  // Initial load
  loadPortfolio(); loadMovers(); loadCongress(); loadFlow(); loadDarkpool(); loadTechnicals();

  // Set intervals
  const timers = [];
  timers.push(setInterval(loadPortfolio, REFRESH_MS['portfolio-pnl']));
  timers.push(setInterval(loadMovers, REFRESH_MS['movers']));
  timers.push(setInterval(loadCongress, REFRESH_MS['congress']));
  timers.push(setInterval(loadFlow, REFRESH_MS['flow']));
  timers.push(setInterval(loadDarkpool, REFRESH_MS['darkpool']));
  timers.push(setInterval(loadTechnicals, REFRESH_MS['technicals']));

  // Pause when tab hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      timers.forEach(t => clearInterval(t));
      timers.length = 0;
    } else {
      loadPortfolio(); loadMovers();
      timers.push(setInterval(loadPortfolio, REFRESH_MS['portfolio-pnl']));
      timers.push(setInterval(loadMovers, REFRESH_MS['movers']));
      timers.push(setInterval(loadCongress, REFRESH_MS['congress']));
      timers.push(setInterval(loadFlow, REFRESH_MS['flow']));
      timers.push(setInterval(loadDarkpool, REFRESH_MS['darkpool']));
      timers.push(setInterval(loadTechnicals, REFRESH_MS['technicals']));
    }
  });
}

startPolling();
