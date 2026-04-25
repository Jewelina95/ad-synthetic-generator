/* ============================================================
   common.js
   Shared navigation, data fetch helpers, Plotly theme defaults.
   Loaded on every page.
   ============================================================ */

/**
 * Inject the shared site header / navigation.
 * Call insertNav('index') / insertNav('data-sources') / insertNav('method') / insertNav('patients')
 * on each page's <body> via DOMContentLoaded.
 */
function insertNav(activePage) {
  const links = [
    { id: 'index',        label: 'Overview',     href: 'index.html' },
    { id: 'data-sources', label: 'Data Sources', href: 'data-sources.html' },
    { id: 'method',       label: 'Method',       href: 'method.html' },
    { id: 'tasks',        label: 'Tasks',        href: 'tasks.html' },
    { id: 'patients',     label: 'Patients',     href: 'patients.html' },
    { id: 'downloads',    label: '📥 Downloads', href: 'downloads.html' },
  ];
  const html = `
    <nav class="nav">
      <div class="nav-inner">
        <a href="index.html" class="nav-brand">
          <span class="nav-brand-mark">AD</span>
          <span>Multimodal Synthetic Data Generator</span>
        </a>
        <div class="nav-links">
          ${links.map(l => `
            <a href="${l.href}" class="${l.id === activePage ? 'active' : ''}">${l.label}</a>
          `).join('')}
        </div>
      </div>
    </nav>
  `;
  // place at top of body
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  document.body.insertBefore(wrap.firstElementChild, document.body.firstChild);
}

/**
 * Site footer — shared across pages.
 */
function insertFooter() {
  const html = `
    <footer class="footer">
      <div class="container">
        <div>AD Multimodal Synthetic Data Generator &middot; v2.2 &middot; Task-centric (VBVR-aligned) &middot; Calibrated by 5 OpenNeuro datasets (n=112)</div>
        <div class="faint mono">Generated 2026-04-25</div>
      </div>
    </footer>
  `;
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  document.body.appendChild(wrap.firstElementChild);
}

/* ----------------------------------------------------------------
   Data loaders
---------------------------------------------------------------- */

/** Fetch JSON, returns parsed object. */
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Fetch failed: ${url} -> ${r.status}`);
  return r.json();
}

/** Fetch a JSONL file, returns array of parsed line objects. */
async function fetchJSONL(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Fetch failed: ${url} -> ${r.status}`);
  const text = await r.text();
  return text.split('\n')
    .map(l => l.trim())
    .filter(Boolean)
    .map(l => JSON.parse(l));
}

/** Fetch a CSV file, returns array of row objects. Numbers auto-parsed. */
async function fetchCSV(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Fetch failed: ${url} -> ${r.status}`);
  const text = await r.text();
  const lines = text.trim().split('\n');
  const header = lines[0].split(',').map(s => s.trim());
  return lines.slice(1).map(line => {
    const cols = line.split(',');
    const obj = {};
    header.forEach((h, i) => {
      const v = cols[i];
      const n = parseFloat(v);
      obj[h] = (!isNaN(n) && v !== '') ? n : v;
    });
    return obj;
  });
}

/** Load all data for a given patient id (e.g. 'P01'). */
async function loadPatient(pid) {
  const base = `data/patients/${pid}`;
  const [persona, progression, surveys, ema, bpsd, notes] = await Promise.all([
    fetchJSON(`${base}/persona.json`),
    fetchCSV (`${base}/progression.csv`),
    fetchJSONL(`${base}/surveys.jsonl`),
    fetchJSONL(`${base}/ema.jsonl`),
    fetchJSONL(`${base}/bpsd_events.jsonl`),
    fetchJSONL(`${base}/notes.jsonl`),
  ]);
  return { pid, persona, progression, surveys, ema, bpsd, notes };
}

/* ----------------------------------------------------------------
   Plotly theme
---------------------------------------------------------------- */

/** Shared dark layout for Plotly. Merge into any layout via spread. */
const PLOT_LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  font: {
    family: '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif',
    color:  '#9BA9B8',
    size:   12,
  },
  margin: { l: 50, r: 18, t: 30, b: 40 },
  xaxis: {
    gridcolor: '#1B232E',
    zerolinecolor: '#243043',
    tickcolor: '#243043',
    linecolor: '#243043',
  },
  yaxis: {
    gridcolor: '#1B232E',
    zerolinecolor: '#243043',
    tickcolor: '#243043',
    linecolor: '#243043',
  },
  legend: {
    bgcolor: 'rgba(17,22,29,0.6)',
    bordercolor: '#243043',
    borderwidth: 1,
    font: { color: '#E6EDF3', size: 11 },
  },
  hoverlabel: {
    bgcolor: '#11161D',
    bordercolor: '#5EEAD4',
    font: { color: '#E6EDF3' },
  },
};

const PLOT_CONFIG = {
  displayModeBar: false,
  responsive: true,
};

/** Plot a chart inside a container, with site theme applied automatically. */
function plot(elId, traces, layoutOverride = {}, configOverride = {}) {
  const el = document.getElementById(elId);
  if (!el) return;
  const layout = deepMerge(structuredClone(PLOT_LAYOUT), layoutOverride);
  const config = { ...PLOT_CONFIG, ...configOverride };
  Plotly.newPlot(el, traces, layout, config);
}

/** Mini-plot helper - tighter margins for in-card charts. */
function plotMini(elId, traces, layoutOverride = {}) {
  const layout = deepMerge(structuredClone(PLOT_LAYOUT), {
    margin: { l: 22, r: 8, t: 6, b: 18 },
    xaxis: { ...PLOT_LAYOUT.xaxis, showticklabels: false },
    yaxis: { ...PLOT_LAYOUT.yaxis, showticklabels: false },
    showlegend: false,
    ...layoutOverride,
  });
  plot(elId, traces, layout);
}

/** Deep merge utility (objects only, arrays replaced). */
function deepMerge(target, src) {
  if (!src) return target;
  for (const k of Object.keys(src)) {
    if (src[k] && typeof src[k] === 'object' && !Array.isArray(src[k])) {
      target[k] = deepMerge(target[k] || {}, src[k]);
    } else {
      target[k] = src[k];
    }
  }
  return target;
}

/* ----------------------------------------------------------------
   Display helpers
---------------------------------------------------------------- */

const ACCENT       = '#5EEAD4';
const ACCENT_2     = '#38BDF8';
const ACCENT_WARM  = '#F59E0B';
const ACCENT_ROSE  = '#F472B6';
const ACCENT_GREEN = '#22C55E';
const ACCENT_GREY  = '#5C6B7C';

const PROGRESSION_LABELS = {
  linear:      'Linear',
  stepwise:    'Stepwise',
  plateau:     'Plateau',
  fluctuation: 'Fluctuation',
  acute_event: 'Acute Event',
};

const PROGRESSION_DESC = {
  linear:      '逐日缓慢退化, 无明显跳变',
  stepwise:    '阶梯式恶化 — 长期稳定, 跳到下一台阶',
  plateau:     '初期下降后进入稳定平台',
  fluctuation: '日间情绪波动叠加慢退化',
  acute_event: '急性事件 (跌倒/谵妄) 后陡降',
};

/** Format a survey JSONL trace for chart display. */
function surveyCols(surveys, key) { return surveys.map(s => s[key]); }

/** EMA daily mean for a given variable (handles missing). */
function emaDailyMean(ema, key) {
  const byDay = {};
  for (const e of ema) {
    if (!byDay[e.day]) byDay[e.day] = [];
    if (e[key] != null) byDay[e.day].push(e[key]);
  }
  const days = Object.keys(byDay).map(Number).sort((a,b)=>a-b);
  return {
    days,
    values: days.map(d => byDay[d].reduce((a,b)=>a+b,0) / byDay[d].length),
  };
}
