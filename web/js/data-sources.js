/* ============================================================
   data-sources.js
   Renders dataset cards and 4 distribution plots for the
   Data Sources page.
   ============================================================ */

/** Static metadata for each OpenNeuro dataset card (matches distributions_master.json keys). */
const DS_META = {
  ds004504: {
    title: 'EEG · AD / FTD / Healthy 三组对照',
    paper: 'Miltiadous et al. 2023, MDPI Data',
    pills: ['EEG 19ch · 500Hz', 'MMSE', 'AD n=36'],
    note: '主要用于 MMSE 三组分布校准 (ctrl 30 / FTD 22.17 / AD 17.75).'
  },
  ds007427: {
    title: 'EEG · 哥伦比亚 paisa 家族性 AD 队列',
    paper: 'Henao Isaza et al. 2026, PLOS ONE',
    pills: ['EEG', 'E280A PSEN1', 'MMSE 子项'],
    note: 'MCI/at-risk 桶用于 MMSE 中度区间校准 (μ=24.0, σ=3.84).'
  },
  ds006095: {
    title: 'EEG + IMU · Mind in Motion 老年步态',
    paper: 'Mind in Motion (UF)',
    pills: ['IMU + EMG', 'MoCA', '老年 n=71'],
    note: '★ 与本项目最相关 — 校准老年 IMU + MoCA baseline.'
  },
  ds004796: {
    title: 'PEARL-Neuro · 中年痴呆风险',
    paper: 'Dzianok & Kublik 2024, Sci Data',
    pills: ['EEG + fMRI', 'APOE 基因', 'BDI'],
    note: '中年 50-60 岁, 用于 SCD / 早期建模 + APOE 风险分层.'
  },
  ds002778: {
    title: 'Resting-state EEG · PD vs Healthy',
    paper: 'UC San Diego, Rockhill et al.',
    pills: ['EEG', 'PD n=15', 'MMSE'],
    note: 'AD 与 PD 鉴别诊断 EEG 标志物对照.'
  },
};

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

async function renderDataSources() {
  const dist = await fetchJSON('data/distributions_master.json');

  // 1. Dataset cards
  const wrap = document.getElementById('dsCards');
  wrap.innerHTML = Object.entries(DS_META).map(([id, m]) => {
    const ds = dist.datasets[id];
    return `
      <div class="ds-card">
        <div class="ds-card-head">
          <span class="ds-id">${id}</span>
          <span class="ds-n">n = ${ds.n_total}</span>
        </div>
        <h4>${m.title}</h4>
        <div class="ds-modality">${ds.modality || ''}</div>
        <div>${(m.pills || []).map(p => `<span class="ds-pill">${p}</span>`).join(' ')}</div>
        <p>${m.note}</p>
        <div class="faint mono" style="font-size: 0.78rem;">${m.paper}</div>
      </div>
    `;
  }).join('');

  // 2. MMSE three-group distribution (Gaussian curves overlay)
  const mmse = dist.combined_mmse_distribution;
  const xs = [];
  for (let v = 0; v <= 30; v += 0.2) xs.push(v);
  const gauss = (mu, sd) => xs.map(x => {
    const z = (x - mu) / sd;
    return Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI));
  });

  const mmseGroups = [
    { key: 'ctrl', label: 'Healthy (ctrl)',   color: ACCENT },
    { key: 'mci',  label: 'MCI / FTD',         color: ACCENT_WARM },
    { key: 'ad',   label: 'AD',                color: ACCENT_ROSE },
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
  const mocaTrace = [{
    x: mocaSamples,
    type: 'histogram',
    name: 'MoCA',
    marker: { color: ACCENT_2, line: { color: '#0B0F14', width: 1 } },
    xbins: { start: 18, end: 30, size: 0.5 },
    hovertemplate: 'MoCA=%{x}<br>count=%{y}<extra></extra>',
  }];
  plot('mocaPlot', mocaTrace, {
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
