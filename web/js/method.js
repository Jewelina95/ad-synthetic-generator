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
  // raw progression: linear 0 -> 1
  const days = Array.from({length: 30}, (_, i) => i);
  const raw = days.map(d => d / 29);
  const reserveCurves = [
    { factor: 0.65, label: 'Reserve 0.65 (高 edu, 掩盖)',  color: ACCENT },
    { factor: 1.00, label: 'Reserve 1.00 (基线)',          color: ACCENT_2 },
    { factor: 1.15, label: 'Reserve 1.15 (低 edu, 显症)',  color: ACCENT_ROSE },
  ];
  const rTraces = [
    {
      x: days, y: raw,
      type: 'scatter', mode: 'lines',
      name: 'raw progression',
      line: { color: '#4D5C70', width: 1.5, dash: 'dash' },
    },
    ...reserveCurves.map(rc => ({
      x: days,
      y: raw.map(v => Math.min(1, v * rc.factor)),
      type: 'scatter', mode: 'lines',
      name: rc.label,
      line: { color: rc.color, width: 2.5 },
    })),
  ];
  plot('reservePlot', rTraces, {
    xaxis: { title: 'Day' },
    yaxis: { title: 'effective progression' },
    legend: { orientation: 'h', y: -0.22, x: 0 },
    margin: { l: 50, r: 18, t: 10, b: 60 },
  });
}
