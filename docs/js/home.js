/* ============================================================
   home.js
   Renders the small MMSE distribution teaser on the index page.
   ============================================================ */

/**
 * Teaser: three Gaussians for ctrl / mci / ad MMSE distributions.
 * Pulls μ/σ from data/distributions_master.json (combined_mmse_distribution).
 */
async function renderHomeMmseTeaser() {
  const dist = await fetchJSON('data/distributions_master.json');
  const mmse = dist.combined_mmse_distribution;

  const xs = [];
  for (let v = 0; v <= 30; v += 0.2) xs.push(v);

  const gauss = (mu, sd) => xs.map(x => {
    const z = (x - mu) / sd;
    return Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI));
  });

  const groups = [
    { key: 'ctrl', label: `Healthy (μ=${mmse.ctrl.mean.toFixed(2)}, n=${mmse.ctrl.n})`, color: ACCENT },
    { key: 'mci',  label: `MCI / FTD (μ=${mmse.mci.mean.toFixed(2)}, n=${mmse.mci.n})`, color: ACCENT_WARM },
    { key: 'ad',   label: `AD (μ=${mmse.ad.mean.toFixed(2)}, n=${mmse.ad.n})`,          color: ACCENT_ROSE },
  ];

  const traces = groups.map(g => ({
    x: xs,
    y: gauss(mmse[g.key].mean, Math.max(mmse[g.key].sd, 0.6)),
    type: 'scatter',
    mode: 'lines',
    name: g.label,
    line: { color: g.color, width: 2.5 },
    fill: 'tozeroy',
    fillcolor: g.color + '22',
    hovertemplate: `MMSE=%{x:.1f}<br>density=%{y:.3f}<extra>${g.label}</extra>`,
  }));

  plot('mmseTeaser', traces, {
    xaxis: { title: 'MMSE', range: [0, 30], dtick: 5 },
    yaxis: { title: 'density', showticklabels: false },
    legend: { orientation: 'h', y: -0.18, x: 0 },
    margin: { l: 40, r: 18, t: 20, b: 50 },
  });
}
