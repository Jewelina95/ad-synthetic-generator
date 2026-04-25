/* ============================================================
   patients.js
   Renders 5 patient cards (each with mini Plotly charts) and a
   detailed modal. Data is fetched from data/patients/P0X/*.
   ============================================================ */

const PIDS = ['P01', 'P02', 'P03', 'P04', 'P05'];

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
  `;

  // Show modal first so layout dimensions are computed
  document.getElementById('modalBackdrop').classList.add('open');

  // Now draw the full plots
  drawModalCharts(p);
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
