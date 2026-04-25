/* ============================================================
   patients.js
   Renders 10 patient cards (each with mini Plotly charts) and a
   detailed modal. Data is fetched from data/patients/P0X/*.
   ============================================================ */

const PIDS = ['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07', 'P08', 'P09', 'P10'];

// In-memory cache so we don't refetch when modal opens
const CACHE = {};

/** ENTRY: render the whole page. */
async function renderPatientsPage() {
  // 1. Load all 5 patients in parallel
  const all = await Promise.all(PIDS.map(loadPatient));
  all.forEach(p => { CACHE[p.pid] = p; });

  // 2. Render cards
  const grid = document.getElementById('patientGrid');
  grid.innerHTML = '';
  for (const p of all) {
    grid.appendChild(buildCard(p));
  }

  // 3. After cards in DOM, draw mini-charts
  for (const p of all) {
    drawCardMiniCharts(p);
  }

  // 4. Modal close handlers
  document.getElementById('modalClose').onclick  = closeModal;
  document.getElementById('modalBackdrop').onclick = (e) => {
    if (e.target.id === 'modalBackdrop') closeModal();
  };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
}

/** Build one patient card DOM node. */
function buildCard(p) {
  const persona = p.persona;
  const reserveLabel = persona.cognitive_reserve_factor < 0.8  ? '强 (掩盖)'
                     : persona.cognitive_reserve_factor < 1.0  ? '中等'
                     : persona.cognitive_reserve_factor < 1.10 ? '基线' : '弱 (显症)';
  const lastSurvey = p.surveys[p.surveys.length - 1];
  const finalMMSE = lastSurvey ? lastSurvey.mmse_estimate.toFixed(1) : '—';

  const tags = [];
  if (persona.bpsd_episodes_total > 0)
    tags.push(`<span class="tag bpsd">${persona.bpsd_episodes_total} BPSD episode(s)</span>`);
  if (p.notes.length > 0)
    tags.push(`<span class="tag note">clinical note · ${p.notes[0].template}</span>`);
  tags.push(`<span class="tag reserve">reserve ${persona.cognitive_reserve_factor.toFixed(2)} · ${reserveLabel}</span>`);

  const noteText = p.notes.length ? p.notes[0].text : '';

  const card = document.createElement('div');
  card.className = 'patient-card';
  card.dataset.pid = persona.patient_id;
  card.innerHTML = `
    <div class="pc-head">
      <div class="pc-id">${persona.patient_id}</div>
      <div class="pc-pattern">${PROGRESSION_LABELS[persona.progression_pattern] || persona.progression_pattern}</div>
    </div>

    <div class="pc-meta">
      <div class="pc-meta-item"><small>Age / Sex</small><span>${persona.age} · ${persona.gender}</span></div>
      <div class="pc-meta-item"><small>Education</small><span>${persona.education_years} yrs</span></div>
      <div class="pc-meta-item"><small>Final MMSE</small><span>${finalMMSE}</span></div>
      <div class="pc-meta-item"><small>Base subject</small><span class="mono" style="font-size:.84rem;">${persona.base_subject}</span></div>
    </div>

    <div class="pc-mini-charts">
      <div class="pc-mini-chart">
        <div class="label">Progression</div>
        <div id="mini-prog-${persona.patient_id}" style="height: 56px;"></div>
      </div>
      <div class="pc-mini-chart">
        <div class="label">MMSE / MoCA</div>
        <div id="mini-survey-${persona.patient_id}" style="height: 56px;"></div>
      </div>
      <div class="pc-mini-chart">
        <div class="label">EMA mood</div>
        <div id="mini-ema-${persona.patient_id}" style="height: 56px;"></div>
      </div>
    </div>

    <div class="pc-tags">${tags.join('')}</div>

    ${noteText ? `<div class="pc-note">"${truncate(noteText, 90)}"</div>` : ''}
  `;
  card.onclick = () => openModal(persona.patient_id);
  return card;
}

/** Truncate string with ellipsis. */
function truncate(s, n) {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

/** Draw the 3 mini-charts inside one card. */
function drawCardMiniCharts(p) {
  const pid = p.persona.patient_id;
  const meta = { color: PATIENT_COLOR[pid] || ACCENT };

  // Progression
  plotMini(`mini-prog-${pid}`, [{
    x: p.progression.map(r => r.day),
    y: p.progression.map(r => r.effective_progression),
    type: 'scatter', mode: 'lines',
    line: { color: meta.color, width: 2, shape: 'spline' },
    fill: 'tozeroy', fillcolor: meta.color + '22',
  }], { yaxis: { range: [-0.05, 1.0], showticklabels: false } });

  // Survey: MMSE + MoCA on twin lines
  const sx = p.surveys.map(s => s.day);
  plotMini(`mini-survey-${pid}`, [
    {
      x: sx, y: p.surveys.map(s => s.mmse_estimate),
      type: 'scatter', mode: 'lines+markers',
      line: { color: ACCENT, width: 2 }, marker: { size: 5, color: ACCENT },
      name: 'MMSE',
    },
    {
      x: sx, y: p.surveys.map(s => s.moca_estimate),
      type: 'scatter', mode: 'lines+markers',
      line: { color: ACCENT_WARM, width: 2 }, marker: { size: 5, color: ACCENT_WARM },
      name: 'MoCA',
    },
  ], { yaxis: { range: [0, 32] } });

  // EMA mood daily mean
  const moodAgg = emaDailyMean(p.ema, 'mood');
  plotMini(`mini-ema-${pid}`, [{
    x: moodAgg.days, y: moodAgg.values,
    type: 'scatter', mode: 'lines',
    line: { color: ACCENT_ROSE, width: 2, shape: 'spline' },
    fill: 'tozeroy', fillcolor: ACCENT_ROSE + '22',
  }], { yaxis: { range: [0, 10] } });
}

const PATIENT_COLOR = {
  P01: ACCENT,
  P02: ACCENT_2,
  P03: ACCENT_WARM,
  P04: ACCENT_ROSE,
  P05: ACCENT_GREEN,
  P06: '#A78BFA', // violet
  P07: '#F87171', // red
  P08: '#34D399', // emerald
  P09: '#60A5FA', // blue
  P10: '#FBBF24', // amber
};

/* ----------------------------------------------------------------
   MODAL
---------------------------------------------------------------- */

/** Open detail modal for one patient. */
function openModal(pid) {
  const p = CACHE[pid];
  if (!p) return;
  const persona = p.persona;

  // Header
  document.getElementById('modalEyebrow').textContent =
    `${PROGRESSION_LABELS[persona.progression_pattern]} · reserve ${persona.cognitive_reserve_factor.toFixed(2)}`;
  document.getElementById('modalTitle').textContent =
    `${pid} · ${persona.age}y ${persona.gender} · edu ${persona.education_years}y`;

  // Body
  const body = document.getElementById('modalBody');
  const noteHtml = p.notes.map(n => `
    <div class="note-box">
      <div class="note-meta">Day ${n.day} · template = "${n.template}"</div>
      <div>${n.text}</div>
    </div>
  `).join('') || '<div class="muted">No clinical note this month.</div>';

  const bpsdHtml = p.bpsd.length
    ? p.bpsd.map(e => `
        <div class="event-card">
          <div class="ev-day">Day ${e.day} · ${String(e.hour).padStart(2,'0')}:00</div>
          <div class="ev-type">${e.type}</div>
          <div class="ev-meta">${e.duration_min} min</div>
          <div class="ev-meta">p=${(+e.progression_at_event).toFixed(2)}</div>
        </div>
      `).join('')
    : '<div class="muted">No BPSD events recorded in 30 days.</div>';

  // Survey table
  const surveyTbl = `
    <table class="tbl">
      <thead><tr><th>Day</th><th>MMSE</th><th>MoCA</th><th>PHQ-9</th></tr></thead>
      <tbody>
        ${p.surveys.map(s => `
          <tr>
            <td class="mono">${s.day}</td>
            <td>${s.mmse_estimate.toFixed(1)}</td>
            <td>${s.moca_estimate.toFixed(1)}</td>
            <td>${s.phq9.toFixed(1)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;

  // Persona summary table
  const personaTbl = `
    <table class="tbl">
      <tbody>
        <tr><th>Patient ID</th><td class="mono">${persona.patient_id}</td>
            <th>Base subject</th><td class="mono">${persona.base_subject}</td></tr>
        <tr><th>Age / Sex</th><td>${persona.age} · ${persona.gender}</td>
            <th>Education</th><td>${persona.education_years} yrs</td></tr>
        <tr><th>Progression</th><td>${PROGRESSION_LABELS[persona.progression_pattern]} <span class="faint">— ${PROGRESSION_DESC[persona.progression_pattern] || ''}</span></td>
            <th>Reserve factor</th><td class="mono">${persona.cognitive_reserve_factor}</td></tr>
        <tr><th>BPSD prone</th><td>${persona.bpsd_prone}</td>
            <th>BPSD episodes</th><td>${persona.bpsd_episodes_total}</td></tr>
      </tbody>
    </table>
  `;

  body.innerHTML = `
    <div class="modal-section">
      <h4>Persona</h4>
      ${personaTbl}
    </div>

    <div class="modal-section">
      <h4>30-day Progression</h4>
      <div class="plot-frame"><div id="m-prog" style="height: 260px;"></div></div>
    </div>

    <div class="modal-section">
      <h4>EMA Time Series (mood / anxiety / sleep / energy)</h4>
      <div class="plot-frame"><div id="m-ema" style="height: 360px;"></div></div>
    </div>

    <div class="modal-section">
      <h4>Weekly Surveys</h4>
      <div class="grid-2" style="grid-template-columns: 1.2fr 1fr; gap: 16px;">
        <div class="plot-frame"><div id="m-survey" style="height: 280px;"></div></div>
        ${surveyTbl}
      </div>
    </div>

    <div class="modal-section">
      <h4>BPSD Events</h4>
      ${bpsdHtml}
    </div>

    <div class="modal-section">
      <h4>Clinical Notes</h4>
      ${noteHtml}
    </div>

    <section class="modal-section sensor-section">
      <h4>📡 真实 Sensor 数据样本 — 退化对比</h4>
      <p class="muted" style="margin: -4px 0 14px;">
        取 walking_normal 任务每 10 秒样本 (50Hz × 500 点), 对比 Day 0 (健康基线) 到 Day 25 (进展) 的真实波形变化
      </p>
      <div class="sensor-grid">
        <div id="sensor-hr-${pid}"   class="sensor-plot"></div>
        <div id="sensor-svm-${pid}"  class="sensor-plot"></div>
        <div id="sensor-gsr-${pid}"  class="sensor-plot"></div>
        <div id="sensor-imu3-${pid}" class="sensor-plot"></div>
      </div>
      <div class="sensor-stats" id="sensor-stats-${pid}">加载 sensor 样本中…</div>
    </section>
  `;

  // Show modal first so layout dimensions are computed
  document.getElementById('modalBackdrop').classList.add('open');

  // Now draw the full plots
  drawModalCharts(p);

  // Async: fetch + draw real sensor waveforms
  renderSensorWaveforms(pid, p);
}

/* ----------------------------------------------------------------
   REAL SENSOR WAVEFORMS (4 panels, fetched per modal open)
---------------------------------------------------------------- */

const SENSOR_SAMPLES_CACHE = {};

const SENSOR_DAY_KEYS   = ['day_0', 'day_7', 'day_14', 'day_25'];
const SENSOR_DAY_LABELS = {
  day_0:  'Day 0 (健康)',
  day_7:  'Day 7',
  day_14: 'Day 14',
  day_25: 'Day 25 (进展)',
};
// cool -> warm gradient: Day 0 cool, Day 25 warm/red
const SENSOR_DAY_COLORS = {
  day_0:  '#5EEAD4',
  day_7:  '#10B981',
  day_14: '#F59E0B',
  day_25: '#EF4444',
};

/** Build a time axis (seconds) of length n with given duration. */
function sensorTimeAxis(n_points, duration_s) {
  const n = Math.max(1, n_points|0);
  const d = +duration_s || 0;
  const out = new Array(n);
  for (let i = 0; i < n; i++) out[i] = (i * d) / n;
  return out;
}

/** Find any BPSD events on a given absolute day (rough match). */
function bpsdOnDay(bpsd, day) {
  return (bpsd || []).filter(e => +e.day === +day);
}

/** Common Plotly layout for a sensor sub-plot. */
function sensorPlotLayout(title, yTitle, extra = {}) {
  return {
    title: { text: title, x: 0, xanchor: 'left',
             font: { color: '#E6EDF3', size: 13 } },
    xaxis: { title: '时间 (秒)' },
    yaxis: { title: yTitle },
    legend: { orientation: 'h', y: -0.25, x: 0, font: { size: 10 } },
    margin: { l: 52, r: 14, t: 32, b: 56 },
    ...extra,
  };
}

/** Format number safely for stats output. */
function fmt(v, digits = 1) {
  if (v == null || !isFinite(v)) return '—';
  return (+v).toFixed(digits);
}
/** Percent change between two numbers. */
function pctChange(a, b) {
  if (a == null || b == null || !isFinite(a) || !isFinite(b) || a === 0) return null;
  return ((b - a) / Math.abs(a)) * 100;
}
function fmtPct(p) {
  if (p == null || !isFinite(p)) return '—';
  const sign = p >= 0 ? '+' : '';
  return `${sign}${p.toFixed(0)}%`;
}

/** Render the 4 sensor waveform plots + stats summary. */
async function renderSensorWaveforms(pid, patient) {
  const statsEl = document.getElementById(`sensor-stats-${pid}`);
  let samples = SENSOR_SAMPLES_CACHE[pid];
  if (!samples) {
    try {
      samples = await fetchJSON(`data/patients/${pid}/sensor_samples.json`);
      SENSOR_SAMPLES_CACHE[pid] = samples;
    } catch (e) {
      const sec = document.querySelector(`#sensor-stats-${pid}`)?.parentElement;
      if (sec) {
        sec.innerHTML = `<h4>📡 真实 Sensor 数据样本 — 退化对比</h4>
                         <p class="muted">无 sensor 样本 (sensor_samples.json 缺失)</p>`;
      }
      return;
    }
  }

  // Days actually present in JSON
  const days = SENSOR_DAY_KEYS.filter(d => samples[d] && samples[d].data);
  if (days.length === 0) {
    if (statsEl) statsEl.textContent = '无可用 sensor 样本';
    return;
  }

  // ---- Plot 1: HR over time ----
  const hrTraces = days.map(d => {
    const s = samples[d];
    return {
      x: sensorTimeAxis(s.n_points, s.duration_s),
      y: s.data.hr_bpm_avg,
      name: SENSOR_DAY_LABELS[d],
      type: 'scatter', mode: 'lines',
      line: { color: SENSOR_DAY_COLORS[d], width: 1.6 },
      hovertemplate: `${SENSOR_DAY_LABELS[d]}<br>t=%{x:.2f}s<br>HR=%{y:.0f} bpm<extra></extra>`,
    };
  });
  plot(`sensor-hr-${pid}`, hrTraces,
    sensorPlotLayout('心率 (HR) — 4 天对比 · HRV 退化',
                     'HR (bpm)'));

  // ---- Plot 2: SVM (movement intensity) ----
  const svmTraces = days.map(d => {
    const s = samples[d];
    return {
      x: sensorTimeAxis(s.n_points, s.duration_s),
      y: s.data.svm,
      name: SENSOR_DAY_LABELS[d],
      type: 'scatter', mode: 'lines',
      line: { color: SENSOR_DAY_COLORS[d], width: 1.4 },
      hovertemplate: `${SENSOR_DAY_LABELS[d]}<br>t=%{x:.2f}s<br>SVM=%{y:.2f}<extra></extra>`,
    };
  });
  plot(`sensor-svm-${pid}`, svmTraces,
    sensorPlotLayout('SVM (合加速度强度) — 4 天对比 · 步态变异',
                     'SVM (m/s²)'));

  // ---- Plot 3: GSR / EDA ----
  // Find BPSD events that fall on a sampled day so we can annotate them
  const bpsdAnnotations = [];
  for (const d of days) {
    const dayNum = samples[d].day;
    const evts = bpsdOnDay(patient && patient.bpsd, dayNum);
    if (evts.length) {
      bpsdAnnotations.push({
        x: 0.5,
        xref: 'paper',
        y: 1.06, yref: 'paper',
        xanchor: 'left',
        text: `⚠ Day ${dayNum} BPSD: ${evts.map(e => e.type).join(', ')}`,
        showarrow: false,
        font: { color: ACCENT_ROSE, size: 10 },
      });
    }
  }
  const gsrTraces = days.map(d => {
    const s = samples[d];
    return {
      x: sensorTimeAxis(s.n_points, s.duration_s),
      y: s.data.gsr_filtered,
      name: SENSOR_DAY_LABELS[d],
      type: 'scatter', mode: 'lines',
      line: { color: SENSOR_DAY_COLORS[d], width: 1.4 },
      hovertemplate: `${SENSOR_DAY_LABELS[d]}<br>t=%{x:.2f}s<br>GSR=%{y:.0f}<extra></extra>`,
    };
  });
  plot(`sensor-gsr-${pid}`, gsrTraces,
    sensorPlotLayout('EDA (gsr_filtered) — 4 天对比 · 老年皮肤干燥',
                     'GSR (filtered)',
                     { annotations: bpsdAnnotations }));

  // ---- Plot 4: IMU 3-axis on the latest day ----
  const lastDay = days[days.length - 1];
  const sLast = samples[lastDay];
  const tAx = sensorTimeAxis(sLast.n_points, sLast.duration_s);
  const imuTraces = [
    { x: tAx, y: sLast.data.imu_ax_mps2, name: 'ax',
      type: 'scatter', mode: 'lines',
      line: { color: ACCENT, width: 1.2 } },
    { x: tAx, y: sLast.data.imu_ay_mps2, name: 'ay',
      type: 'scatter', mode: 'lines',
      line: { color: ACCENT_WARM, width: 1.2 } },
    { x: tAx, y: sLast.data.imu_az_mps2, name: 'az',
      type: 'scatter', mode: 'lines',
      line: { color: ACCENT_ROSE, width: 1.2 } },
  ];
  plot(`sensor-imu3-${pid}`, imuTraces,
    sensorPlotLayout(`IMU 三轴加速度 — ${SENSOR_DAY_LABELS[lastDay]} 单天细节`,
                     'a (m/s²)'));

  // ---- Stats summary ----
  const d0  = samples.day_0;
  const d25 = samples.day_25;
  if (d0 && d25 && statsEl) {
    const hr0   = d0.hr_stats || {}, hr1 = d25.hr_stats || {};
    const svm0  = d0.svm_stats || {}, svm1 = d25.svm_stats || {};
    const gsr0  = d0.gsr_stats || {}, gsr1 = d25.gsr_stats || {};

    const lines = [
      `退化对比 (Day 0 → Day 25):`,
      `  · HR mean : ${fmt(hr0.mean, 1)} → ${fmt(hr1.mean, 1)} bpm  (Δ ${fmt((hr1.mean ?? 0) - (hr0.mean ?? 0), 1)})`,
      `  · HR std  : ${fmt(hr0.std,  2)} → ${fmt(hr1.std,  2)}      (${fmtPct(pctChange(hr0.std,  hr1.std))}, HRV 退化)`,
      `  · SVM std : ${fmt(svm0.std, 2)} → ${fmt(svm1.std, 2)}      (${fmtPct(pctChange(svm0.std, svm1.std))}, 步态变异)`,
      `  · GSR mean: ${fmt(gsr0.mean, 0)} → ${fmt(gsr1.mean, 0)}    (${fmtPct(pctChange(gsr0.mean, gsr1.mean))}, 皮肤干燥)`,
    ];
    statsEl.textContent = lines.join('\n');
  } else if (statsEl) {
    statsEl.textContent = '统计 (Day 0 / Day 25 缺失, 跳过对比)';
  }
}

/** Draw the 3 large plots inside the modal. */
function drawModalCharts(p) {
  const pid = p.persona.patient_id;
  const meta = { color: PATIENT_COLOR[pid] || ACCENT };

  // Mark BPSD events on progression chart with vertical lines
  const bpsdShapes = p.bpsd.map(e => ({
    type: 'line', x0: e.day, x1: e.day, y0: 0, y1: 1, yref: 'paper',
    line: { color: ACCENT_ROSE, width: 1.5, dash: 'dot' },
  }));
  const bpsdAnnotations = p.bpsd.map(e => ({
    x: e.day, y: 1, yref: 'paper', xanchor: 'left', yanchor: 'top',
    text: ` ${e.type}`,
    showarrow: false, font: { color: ACCENT_ROSE, size: 10 },
  }));

  plot('m-prog', [
    {
      x: p.progression.map(r => r.day),
      y: p.progression.map(r => r.raw_progression),
      type: 'scatter', mode: 'lines',
      name: 'raw progression',
      line: { color: '#4D5C70', width: 1.5, dash: 'dash' },
    },
    {
      x: p.progression.map(r => r.day),
      y: p.progression.map(r => r.effective_progression),
      type: 'scatter', mode: 'lines+markers',
      name: 'effective progression',
      line: { color: meta.color, width: 2.5, shape: 'spline' },
      marker: { size: 5, color: meta.color },
      fill: 'tozeroy', fillcolor: meta.color + '20',
    },
  ], {
    xaxis: { title: 'day', dtick: 5 },
    yaxis: { title: 'progression [0,1]', range: [-0.05, 1.05] },
    shapes: bpsdShapes,
    annotations: bpsdAnnotations,
    legend: { orientation: 'h', y: -0.18, x: 0 },
    margin: { l: 50, r: 18, t: 10, b: 50 },
  });

  // EMA: 4 daily-mean lines
  const moodA   = emaDailyMean(p.ema, 'mood');
  const anxA    = emaDailyMean(p.ema, 'anxiety');
  const sleepA  = emaDailyMean(p.ema, 'sleep_quality');
  const energyA = emaDailyMean(p.ema, 'energy');
  plot('m-ema', [
    { x: moodA.days,   y: moodA.values,   name: 'mood',          type:'scatter', mode:'lines+markers',
      line: { color: ACCENT_ROSE, width: 2, shape: 'spline' }, marker:{size:4,color:ACCENT_ROSE} },
    { x: anxA.days,    y: anxA.values,    name: 'anxiety',       type:'scatter', mode:'lines+markers',
      line: { color: ACCENT_WARM, width: 2, shape: 'spline' }, marker:{size:4,color:ACCENT_WARM} },
    { x: sleepA.days,  y: sleepA.values,  name: 'sleep quality', type:'scatter', mode:'lines+markers',
      line: { color: ACCENT,      width: 2, shape: 'spline' }, marker:{size:4,color:ACCENT} },
    { x: energyA.days, y: energyA.values, name: 'energy',        type:'scatter', mode:'lines+markers',
      line: { color: ACCENT_2,    width: 2, shape: 'spline' }, marker:{size:4,color:ACCENT_2} },
  ], {
    xaxis: { title: 'day', dtick: 5 },
    yaxis: { title: 'self-report (0–10)', range: [0, 10] },
    legend: { orientation: 'h', y: -0.18, x: 0 },
    margin: { l: 50, r: 18, t: 10, b: 50 },
  });

  // Survey full
  const sx = p.surveys.map(s => s.day);
  plot('m-survey', [
    { x: sx, y: p.surveys.map(s => s.mmse_estimate), type:'scatter', mode:'lines+markers',
      name: 'MMSE (0–30)', line: {color: ACCENT, width: 2}, marker:{size:7,color:ACCENT}, yaxis:'y' },
    { x: sx, y: p.surveys.map(s => s.moca_estimate), type:'scatter', mode:'lines+markers',
      name: 'MoCA (0–30)', line: {color: ACCENT_WARM, width: 2}, marker:{size:7,color:ACCENT_WARM}, yaxis:'y' },
    { x: sx, y: p.surveys.map(s => s.phq9), type:'scatter', mode:'lines+markers',
      name: 'PHQ-9 (0–27)', line: {color: ACCENT_ROSE, width: 2, dash: 'dot'},
      marker:{size:7,color:ACCENT_ROSE}, yaxis:'y2' },
  ], {
    xaxis: { title: 'day', dtick: 7 },
    yaxis: { title: 'MMSE / MoCA', range: [0, 32], side: 'left' },
    yaxis2: {
      title: 'PHQ-9', range: [0, 27],
      overlaying: 'y', side: 'right',
      gridcolor: 'rgba(0,0,0,0)', zerolinecolor: '#243043',
      tickcolor: '#243043', linecolor: '#243043',
      tickfont: { color: ACCENT_ROSE },
      titlefont: { color: ACCENT_ROSE },
    },
    legend: { orientation: 'h', y: -0.22, x: 0 },
    margin: { l: 50, r: 50, t: 10, b: 60 },
  });
}

function closeModal() {
  document.getElementById('modalBackdrop').classList.remove('open');
}
