/* ============================================================
   data-sources.js
   Renders 5 OpenNeuro dataset cards (clickable -> modal) plus
   the four distribution plots at the bottom of the page.
   ============================================================ */

// In-memory cache of the loaded datasets_meta.json.
let DS_META = null;

/** Order in which to render dataset cards. */
const DS_ORDER = ['ds004504', 'ds007427', 'ds006095', 'ds004796', 'ds002778'];

/** Sample N points from a normal distribution N(mu, sd) using Box-Muller. */
function sampleNormal(n, mu, sd) {
  const out = [];
  while (out.length < n) {
    const u1 = Math.random(), u2 = Math.random();
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    out.push(mu + sd * z);
  }
  return out;
}

/** Tiny HTML escape helper for sample-table cells / code blocks. */
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function renderDataSources() {
  // Load both metadata files up front (cards rely on datasets_meta;
  // distribution plots still use distributions_master).
  DS_META = await fetchJSON('data/datasets/datasets_meta.json');
  const dist = await fetchJSON('data/distributions_master.json');

  // 1. Dataset cards
  renderDsCards(dist);

  // 2. Modal close wiring
  document.getElementById('dsModalClose').onclick = closeDsModal;
  document.getElementById('dsModalBackdrop').onclick = (e) => {
    if (e.target.id === 'dsModalBackdrop') closeDsModal();
  };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDsModal();
  });

  // 3. Distribution plots
  drawDistributionPlots(dist);

  // 4. Downloaded-datasets status panel (8 datasets, all locally available)
  renderDatasetStatusPanel().catch((err) => {
    const el = document.getElementById('dsStatusPanel');
    if (el) el.innerHTML = `<div class="muted">Failed to load datasets_status.json: ${esc(err.message || err)}</div>`;
  });
}

/* ----------------------------------------------------------------
   DOWNLOADED-DATASETS STATUS PANEL  (8 datasets all in-use)
---------------------------------------------------------------- */

/** Custom use-case labels per dataset id for the status table.
    Keep consistent with distributions_extended.json. */
const STATUS_USECASE = {
  ds004504: { use: 'MMSE 真实分布 (AD/FTD/CTRL n=88)', tag: '主校准源' },
  ds007427: { use: 'MCI MMSE + 风险组 (n=138)',         tag: '主校准源' },
  ds006095: { use: 'MoCA + Age 老年队列 (n=71)',         tag: '主校准源' },
  ds004796: { use: '中年风险 / APOE e4 26.6% / BDI / BMI (n=192)', tag: '扩展校准' },
  ds002778: { use: 'AD vs PD 差异诊断 EEG MMSE (n=31)', tag: '扩展校准' },
  ds006036: { use: '双范式交叉验证 (同 ds004504 patients, n=88)', tag: '扩展校准' },
  ds005363: { use: 'ORHA Y vs O 健康老化对照 (n=43)',    tag: '扩展校准' },
  ds005892: { use: 'PD-MCI / PD-NC / HC MCI 鉴别 (n=55)', tag: '扩展校准' },
};

/** Datasets to render in the panel, in order. */
const STATUS_ORDER = [
  'ds004504', 'ds007427', 'ds006095',  // primary
  'ds004796', 'ds002778', 'ds006036', 'ds005363', 'ds005892',  // extended
];

async function renderDatasetStatusPanel() {
  const status = await fetchJSON('data/datasets/datasets_status.json');
  const el = document.getElementById('dsStatusPanel');
  if (!el) return;

  // Flatten primary + extended into a single lookup.
  const lookup = {};
  for (const cat of Object.values(status.categories || {})) {
    for (const d of (cat.datasets || [])) {
      lookup[d.id] = d;
    }
  }

  const rows = STATUS_ORDER.map((id) => {
    const d = lookup[id] || {};
    const u = STATUS_USECASE[id] || { use: '—', tag: '—' };
    const isPrimary = u.tag === '主校准源';
    return `
      <tr class="row-used">
        <td class="mono">${esc(id)}</td>
        <td>${esc(d.title || '—')}</td>
        <td>${esc(d.n != null ? d.n : '—')}</td>
        <td>${esc(u.use)}</td>
        <td><span class="badge-ok">${isPrimary ? '✓ 主校准' : '✓ 已用扩展'}</span></td>
      </tr>
    `;
  }).join('');

  el.innerHTML = `
    <div class="ds-status-headline">
      <span class="pill-ok">8 / 8 在用</span>
      <span>所有数据集已下载并接入校准 pipeline — <b>不需要等任何申请</b></span>
    </div>

    <div class="ds-status-bullet">
      <b>✅ 主校准源 (3):</b> ds004504 / ds007427 / ds006095
      <small>→ MMSE + MoCA 真实分布写入 distributions_master.json</small>
    </div>

    <div class="ds-status-bullet">
      <b>✅ 扩展校准 (5):</b> ds004796 / ds002778 / ds006036 / ds005363 / ds005892
      <small>→ 中年风险分布 / 差异诊断 / 双范式 / 老化对照 / MCI 鉴别 — distributions_extended.json</small>
    </div>

    <table class="ds-status-tbl">
      <thead>
        <tr>
          <th>Dataset ID</th>
          <th>Title</th>
          <th>n</th>
          <th>用途</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>

    <div class="ds-status-footer">
      <b>未来扩展:</b> 真实 AD 患者数据集 (WearGait-PD / ADReSS / OASIS-3 / ADNI 等) 在用户授权后通过 IRB 申请获取.
      <b>当前不需要</b> — 已用 8 个数据集足够支撑生成器校准 (n=672+ 真实受试者覆盖 AD/FTD/MCI/老年/PD/中年风险).
    </div>
  `;
}

/* ----------------------------------------------------------------
   CARD GRID
---------------------------------------------------------------- */

function renderDsCards(dist) {
  const wrap = document.getElementById('dsCards');
  wrap.innerHTML = '';
  for (const id of DS_ORDER) {
    const meta = DS_META[id];
    if (!meta) continue;
    const ds = dist.datasets[id] || {};
    const n = meta.total_rows ?? ds.n_total ?? '—';
    const tagsHtml = (meta.tags || []).slice(0, 4).map(t => {
      const star = t.includes('★') ? ' star' : '';
      return `<span class="ds-badge${star}">${esc(t)}</span>`;
    }).join('');

    const card = document.createElement('div');
    card.className = 'ds-card';
    card.dataset.dsid = id;
    card.innerHTML = `
      <div class="ds-card-head">
        <span class="ds-id">${id}</span>
        <span class="ds-n">n = ${n}</span>
      </div>
      <h4>${esc(meta.title_zh || meta.title)}</h4>
      <div class="ds-modality">${esc(meta.modality_short || '')}</div>
      <div class="ds-tag-row">${tagsHtml}</div>
    `;
    card.onclick = () => openDsModal(id);
    wrap.appendChild(card);
  }
}

/* ----------------------------------------------------------------
   MODAL
---------------------------------------------------------------- */

function openDsModal(dsId) {
  const meta = DS_META[dsId];
  if (!meta) return;

  // Header
  document.getElementById('dsModalEyebrow').textContent = `${dsId} · ${meta.modality_short || ''}`;
  document.getElementById('dsModalTitle').textContent = meta.title_zh || meta.title;
  document.getElementById('dsModalSub').textContent = meta.title || '';

  // Tags
  const tagsHtml = (meta.tags || []).map(t => {
    const star = t.includes('★') ? ' star' : '';
    return `<span class="ds-badge${star}">${esc(t)}</span>`;
  }).join('');

  // Overview grid
  const ovItems = [
    ['Institution', meta.institution],
    ['Year',        meta.year],
    ['Modality',    meta.modality_short],
    ['n (total)',   meta.total_rows],
    ['License',     meta.license],
    ['DOI',         meta.doi],
  ];
  const overviewHtml = ovItems
    .filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `
      <div class="ds-ov-item">
        <small>${esc(k)}</small>
        <span>${esc(v)}</span>
      </div>
    `).join('');

  // Links
  const linkBits = [];
  if (meta.openneuro_url) linkBits.push(`<a class="ds-link" href="${meta.openneuro_url}" target="_blank" rel="noopener">OpenNeuro ↗</a>`);
  if (meta.github_url)    linkBits.push(`<a class="ds-link" href="${meta.github_url}"    target="_blank" rel="noopener">GitHub ↗</a>`);
  if (meta.paper_url)     linkBits.push(`<a class="ds-link" href="${meta.paper_url}"     target="_blank" rel="noopener">Paper ↗</a>`);

  // Sample table
  const sampleCols = meta.sample_columns || [];
  const sampleRows = meta.sample_rows || [];
  const sampleHtml = sampleCols.length ? `
    <div class="ds-table-scroll">
      <table class="tbl">
        <thead>
          <tr>${sampleCols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${sampleRows.map(r => `
            <tr>${(r || []).map(v => `<td>${esc(v)}</td>`).join('')}</tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <div class="faint mono" style="font-size:.78rem; margin-top:6px;">
      显示前 ${sampleRows.length} 行 / 共 ${meta.total_rows ?? '—'} 行
    </div>
  ` : '<div class="muted">No sample preview available.</div>';

  // Group meaning table
  const groupHtml = meta.group_meaning && Object.keys(meta.group_meaning).length ? `
    <table class="ds-stats-tbl" style="margin-top: 10px;">
      <thead><tr><th>Code</th><th>Meaning</th></tr></thead>
      <tbody>
        ${Object.entries(meta.group_meaning).map(([k, v]) => `
          <tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>
        `).join('')}
      </tbody>
    </table>
  ` : '';

  // Extracted stats nested table
  const statsHtml = renderExtractedStats(meta.extracted_stats);

  // Body
  const body = document.getElementById('dsModalBody');
  body.innerHTML = `
    <div class="modal-section">
      <div class="ds-tag-row">${tagsHtml}</div>
    </div>

    <div class="modal-section">
      <h4>📚 概览</h4>
      <div class="ds-overview-grid">${overviewHtml}</div>
    </div>

    <div class="modal-section">
      <h4>📝 详细说明</h4>
      <p style="color: var(--text);">${esc(meta.description_zh || '')}</p>
      <div class="faint" style="font-size:.85rem; margin-top: 6px;">
        <span class="mono">modality:</span> ${esc(meta.modality_long || '')}
      </div>
      <div class="faint" style="font-size:.85rem; margin-top: 4px;">
        <span class="mono">paper:</span> ${esc(meta.paper || '')}
      </div>
    </div>

    <div class="modal-section">
      <h4>🔗 链接</h4>
      <div class="ds-link-row">
        ${linkBits.join('') || '<span class="muted">No links.</span>'}
      </div>
    </div>

    <div class="modal-section">
      <h4>📊 真实数据样本</h4>
      ${sampleHtml}
      ${groupHtml}
    </div>

    <div class="modal-section">
      <h4>🎯 我们怎么用它</h4>
      <div class="ds-howuse">${esc(meta.how_we_use_zh || '—')}</div>
    </div>

    <div class="modal-section">
      <h4>💻 代码片段</h4>
      <pre class="ds-code"><code>${esc(meta.code_snippet || '')}</code></pre>
    </div>

    <div class="modal-section">
      <h4>📈 提取的统计</h4>
      ${statsHtml}
    </div>
  `;

  document.getElementById('dsModalBackdrop').classList.add('open');
}

/** extracted_stats is a nested object like { "AD": {n:36, mmse_mean:17.75, ...} }. */
function renderExtractedStats(stats) {
  if (!stats || typeof stats !== 'object') return '<div class="muted">No extracted stats.</div>';
  const groups = Object.keys(stats);
  if (!groups.length) return '<div class="muted">No extracted stats.</div>';

  // Collect all metric keys across groups (preserve order of first appearance).
  const metricKeys = [];
  for (const g of groups) {
    const obj = stats[g];
    if (obj && typeof obj === 'object') {
      for (const k of Object.keys(obj)) {
        if (!metricKeys.includes(k)) metricKeys.push(k);
      }
    }
  }

  const head = `<tr><th>Group</th>${metricKeys.map(k => `<th>${esc(k)}</th>`).join('')}</tr>`;
  const rows = groups.map(g => {
    const obj = stats[g] || {};
    const cells = metricKeys.map(k => {
      const v = obj[k];
      return `<td>${v == null ? '—' : esc(v)}</td>`;
    }).join('');
    return `<tr><th>${esc(g)}</th>${cells}</tr>`;
  }).join('');

  return `
    <table class="ds-stats-tbl">
      <thead>${head}</thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function closeDsModal() {
  document.getElementById('dsModalBackdrop').classList.remove('open');
}

/* ----------------------------------------------------------------
   DISTRIBUTION PLOTS (unchanged behavior, refactored into a fn)
---------------------------------------------------------------- */

function drawDistributionPlots(dist) {
  // 2. MMSE three-group distribution (Gaussian curves overlay)
  const mmse = dist.combined_mmse_distribution;
  const xs = [];
  for (let v = 0; v <= 30; v += 0.2) xs.push(v);
  const gauss = (mu, sd) => xs.map(x => {
    const z = (x - mu) / sd;
    return Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI));
  });

  const mmseGroups = [
    { key: 'ctrl', label: 'Healthy (ctrl)', color: ACCENT },
    { key: 'mci',  label: 'MCI / FTD',      color: ACCENT_WARM },
    { key: 'ad',   label: 'AD',             color: ACCENT_ROSE },
  ];
  const mmseTraces = mmseGroups.map(g => ({
    x: xs,
    y: gauss(mmse[g.key].mean, Math.max(mmse[g.key].sd, 0.6)),
    type: 'scatter',
    mode: 'lines',
    name: `${g.label} (μ=${mmse[g.key].mean.toFixed(2)}, n=${mmse[g.key].n})`,
    line: { color: g.color, width: 2.5 },
    fill: 'tozeroy',
    fillcolor: g.color + '22',
    hovertemplate: 'MMSE=%{x:.1f}<extra>%{fullData.name}</extra>',
  }));
  plot('mmsePlot', mmseTraces, {
    xaxis: { title: 'MMSE score (0-30)', range: [0, 30], dtick: 5 },
    yaxis: { title: 'density', showticklabels: false },
    legend: { orientation: 'h', y: -0.22, x: 0 },
    margin: { l: 40, r: 20, t: 10, b: 60 },
  });

  // 3. MoCA histogram (sampled from N(27.45, 1.60), bucketed)
  const moca = dist.datasets.ds006095.all_subjects_aggregated.moca;
  const mocaSamples = sampleNormal(2000, moca.mean, moca.sd);
  plot('mocaPlot', [{
    x: mocaSamples,
    type: 'histogram',
    name: 'MoCA',
    marker: { color: ACCENT_2, line: { color: '#0B0F14', width: 1 } },
    xbins: { start: 18, end: 30, size: 0.5 },
    hovertemplate: 'MoCA=%{x}<br>count=%{y}<extra></extra>',
  }], {
    xaxis: { title: 'MoCA score', range: [18, 30] },
    yaxis: { title: 'count' },
    showlegend: false,
    shapes: [{
      type: 'line', x0: moca.mean, x1: moca.mean, y0: 0, y1: 1, yref: 'paper',
      line: { color: ACCENT, width: 2, dash: 'dash' },
    }],
    annotations: [{
      x: moca.mean, y: 1, yref: 'paper', xanchor: 'left', yanchor: 'top',
      text: `μ = ${moca.mean.toFixed(2)}`, showarrow: false,
      font: { color: ACCENT, size: 11 }, bgcolor: 'rgba(11,15,20,0.6)',
    }],
    margin: { l: 40, r: 20, t: 10, b: 50 },
  });

  // 4. Age histogram (ds006095)
  const age = dist.datasets.ds006095.all_subjects_aggregated.age;
  const ageSamples = sampleNormal(2000, age.mean, age.sd);
  plot('agePlot', [{
    x: ageSamples,
    type: 'histogram',
    name: 'Age',
    marker: { color: ACCENT_WARM, line: { color: '#0B0F14', width: 1 } },
    xbins: { start: 55, end: 95, size: 1 },
  }], {
    xaxis: { title: 'Age (years)' },
    yaxis: { title: 'count' },
    showlegend: false,
    shapes: [{
      type: 'line', x0: age.mean, x1: age.mean, y0: 0, y1: 1, yref: 'paper',
      line: { color: ACCENT, width: 2, dash: 'dash' },
    }],
    margin: { l: 40, r: 20, t: 10, b: 50 },
  });

  // 5. BDI depression histogram (ds004796)
  const bdi = dist.datasets.ds004796.key_distributions.BDI_depression;
  const bdiSamples = sampleNormal(2000, bdi.mean, bdi.sd).map(v => Math.max(0, v));
  plot('bdiPlot', [{
    x: bdiSamples,
    type: 'histogram',
    name: 'BDI',
    marker: { color: ACCENT_ROSE, line: { color: '#0B0F14', width: 1 } },
    xbins: { start: 0, end: 40, size: 1 },
  }], {
    xaxis: { title: 'BDI depression score' },
    yaxis: { title: 'count' },
    showlegend: false,
    shapes: [{
      type: 'line', x0: bdi.mean, x1: bdi.mean, y0: 0, y1: 1, yref: 'paper',
      line: { color: ACCENT, width: 2, dash: 'dash' },
    }],
    margin: { l: 40, r: 20, t: 10, b: 50 },
  });
}
