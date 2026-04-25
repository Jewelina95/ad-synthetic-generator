/* ============================================================
   method.js
   - Plot 5 progression curves overlaid (real CSV data from each
     P0X/progression.csv)
   - Plot reserve effect (3 curves with different reserve factors)
   ============================================================ */

const PATIENT_PATTERN_COLOR = {
  P01: { pattern: 'linear',      color: ACCENT      },
  P02: { pattern: 'stepwise',    color: ACCENT_2    },
  P03: { pattern: 'plateau',     color: ACCENT_WARM },
  P04: { pattern: 'fluctuation', color: ACCENT_ROSE },
  P05: { pattern: 'acute_event', color: ACCENT_GREEN},
};

async function renderMethod() {
  // 1. Load all 5 patients' progression.csv in parallel
  const pids = ['P01', 'P02', 'P03', 'P04', 'P05'];
  const progressions = await Promise.all(pids.map(p =>
    fetchCSV(`data/patients/${p}/progression.csv`)
  ));

  // overlay traces
  const traces = pids.map((pid, i) => {
    const meta = PATIENT_PATTERN_COLOR[pid];
    const rows = progressions[i];
    return {
      x: rows.map(r => r.day),
      y: rows.map(r => r.effective_progression),
      type: 'scatter',
      mode: 'lines+markers',
      name: `${pid} · ${meta.pattern}`,
      line: { color: meta.color, width: 2.5, shape: 'spline' },
      marker: { size: 5, color: meta.color },
      hovertemplate: `day=%{x}<br>progression=%{y:.3f}<extra>${pid} ${meta.pattern}</extra>`,
    };
  });

  plot('progressionPlot', traces, {
    xaxis: { title: 'Day (0–29)', dtick: 5 },
    yaxis: { title: 'effective progression', range: [-0.05, 1.0] },
    legend: { orientation: 'h', y: -0.18, x: 0 },
    margin: { l: 50, r: 18, t: 10, b: 60 },
  });

  // 2. Reserve effect plot
  // x-axis: raw_progression (0 → 1, 同一疾病严重程度)
  // y-axis: effective_progression (临床表现) = min(1, raw × factor)
  // 5 条线对应 5 档教育/储备因子, 颜色冷→暖映射储备强→弱
  const rawP = Array.from({length: 30}, (_, i) => i / 29);
  const reserves = [
    { name: '教育 ≥16年 (强储备, 掩盖)', factor: 0.65, color: '#3B82F6' },
    { name: '教育 12年',                 factor: 0.85, color: '#10B981' },
    { name: '教育 9年 (中性)',           factor: 1.00, color: '#A1A1AA' },
    { name: '教育 6年',                   factor: 1.15, color: '#F59E0B' },
    { name: '文盲 (弱储备, 显症)',       factor: 1.25, color: '#EF4444' },
  ];

  const rTraces = reserves.map(r => ({
    x: rawP,
    y: rawP.map(p => Math.min(1, p * r.factor)),
    type: 'scatter',
    mode: 'lines',
    name: r.name,
    line: { color: r.color, width: 2.5, shape: 'spline' },
    hovertemplate: `raw=%{x:.2f}<br>effective=%{y:.2f}<extra>${r.name}</extra>`,
  }));

  // y = x 中性参考虚线 (reserve=1 时的轨迹)
  rTraces.push({
    x: [0, 1],
    y: [0, 1],
    type: 'scatter',
    mode: 'lines',
    name: 'y = x (无储备效应)',
    line: { color: '#5C6B7C', width: 1, dash: 'dot' },
    hoverinfo: 'skip',
  });

  // 关键 annotation: 在 raw=0.6 处展示高/低教育的 effective 差异
  const annotations = [
    {
      x: 0.6, y: 0.6 * 0.65,
      text: '同 raw=0.6,<br>edu≥16 → eff≈0.39<br>(临床表现轻)',
      showarrow: true, arrowhead: 2, arrowcolor: '#3B82F6',
      ax: -70, ay: -40,
      font: { size: 11, color: '#3B82F6' },
      bgcolor: 'rgba(17,22,29,0.7)', bordercolor: '#3B82F6', borderwidth: 1,
    },
    {
      x: 0.6, y: 0.6 * 1.25,
      text: '文盲 → eff≈0.75<br>(临床表现重)',
      showarrow: true, arrowhead: 2, arrowcolor: '#EF4444',
      ax: 70, ay: 30,
      font: { size: 11, color: '#EF4444' },
      bgcolor: 'rgba(17,22,29,0.7)', bordercolor: '#EF4444', borderwidth: 1,
    },
  ];

  plot('reservePlot', rTraces, {
    xaxis: { title: 'raw_progression (实际疾病进展)', range: [0, 1], dtick: 0.2 },
    yaxis: { title: 'effective_progression (临床表现)', range: [0, 1], dtick: 0.2 },
    legend: { orientation: 'h', y: -0.22, x: 0 },
    margin: { l: 55, r: 18, t: 10, b: 70 },
    annotations,
    shapes: [
      // raw=0.6 的垂直参考线, 突出 annotation 位置
      {
        type: 'line', x0: 0.6, x1: 0.6, y0: 0, y1: 1,
        line: { color: '#5C6B7C', width: 1, dash: 'dash' },
      },
    ],
  });
}
