/* ============================================================
   tasks.js
   Renders 4 task cards (one per VBVR-style task) and a modal
   showing patient list, file structure, CSV columns. Data fetched
   from data/tasks_summary.json (and falls back to manifest.json).
   ============================================================ */

const TASK_META = {
  walking_normal: {
    icon: '🚶',
    short_zh: '正常行走',
    desc: '日常自然步行 60 秒. 主要观察步态参数 — svm_std (变异度), 步频, jerk. ' +
          '退化敏感度高: 早期 AD 已可见步态变异度↑, 步频↓.',
    column_focus: ['svm', 'step_freq', 'jerk', 'imu_xyz'],
  },
  walking_dual_task: {
    icon: '🤹',
    short_zh: '双任务行走',
    desc: '行走同时执行认知任务 (倒数, 命名). 双任务条件下步态退化最显著, ' +
          '认知-运动耦合是 AD 早期诊断的关键 marker (cognitive-motor interference).',
    column_focus: ['svm', 'step_freq', 'jerk', 'gait_cv'],
  },
  balance_standing: {
    icon: '🧍',
    short_zh: '站立平衡',
    desc: '闭眼站立 60 秒平衡评估. 摆动量 (sway area, COP path) 反映前庭/小脑通路. ' +
          'AD 患者跌倒风险与此项强相关.',
    column_focus: ['svm', 'sway', 'imu_xyz'],
  },
  hand_fine_motor: {
    icon: '✋',
    short_zh: '手部精细运动',
    desc: '手部精细操作 (拿杯/写字/抓握). 反映上肢神经控制. ' +
          '8/10 患者参与 (P03 / P06 因 base_subject 设置跳过).',
    column_focus: ['imu_xyz', 'jerk', 'tremor_hz'],
  },
};

const TASK_ORDER = ['walking_normal', 'walking_dual_task', 'balance_standing', 'hand_fine_motor'];

/* Sample CSV downloads (~360 KB each, first 40s of day = 2000 rows @ 50Hz).
   walking_normal has 8 cross-comparison samples (Day 0/25 + multiple patients);
   other tasks have a single P01 day00 sample. */
const SAMPLE_DOWNLOADS = {
  walking_normal: [
    { file: 'walking_normal_P01_day00_sample.csv', label: 'P01 · Day 00 (baseline)',    size: '349 KB' },
    { file: 'walking_normal_P01_day25_sample.csv', label: 'P01 · Day 25 (progression)', size: '362 KB' },
    { file: 'walking_normal_P02_day14_sample.csv', label: 'P02 · Day 14',               size: '355 KB' },
    { file: 'walking_normal_P02_day25_sample.csv', label: 'P02 · Day 25',               size: '352 KB' },
    { file: 'walking_normal_P03_day25_sample.csv', label: 'P03 · Day 25',               size: '355 KB' },
    { file: 'walking_normal_P09_day25_sample.csv', label: 'P09 · Day 25',               size: '354 KB' },
  ],
  walking_dual_task: [
    { file: 'walking_dual_task_P01_day00_sample.csv', label: 'P01 · Day 00', size: '349 KB' },
  ],
  balance_standing: [
    { file: 'balance_standing_P01_day00_sample.csv', label: 'P01 · Day 00', size: '353 KB' },
  ],
  hand_fine_motor: [
    { file: 'hand_fine_motor_P01_day00_sample.csv', label: 'P01 · Day 00', size: '353 KB' },
  ],
};

/** Returns the primary (P01 day00) sample download for a task, or null. */
function primarySampleFor(taskId) {
  const list = SAMPLE_DOWNLOADS[taskId] || [];
  return list.find(s => /P01_day00/.test(s.file)) || list[0] || null;
}

let TASK_CACHE = null;

/* -------------- ENTRY -------------- */

async function renderTasksPage() {
  let tasks;
  try {
    tasks = await fetchJSON('data/tasks_summary.json');
  } catch (e) {
    // fallback to manifest
    try {
      const m = await fetchJSON('data/manifest.json');
      tasks = (m.tasks || []).map(t => ({
        task_id: t.task_id,
        name_zh: t.name_zh,
        n_patients: t.n_patients,
        n_files: t.n_files,
        n_days_per_patient: t.n_days_per_patient,
        patients: t.patients,
        size_mb: t.total_size_mb,
      }));
    } catch (e2) {
      document.getElementById('taskGrid').innerHTML =
        '<div class="muted">Failed to load tasks_summary.json or manifest.json.</div>';
      return;
    }
  }

  // Sort by canonical order
  tasks.sort((a, b) => TASK_ORDER.indexOf(a.task_id) - TASK_ORDER.indexOf(b.task_id));
  TASK_CACHE = tasks;

  // Header stats
  const totalFiles = tasks.reduce((s, t) => s + (t.n_files || 0), 0);
  const totalSize = tasks.reduce((s, t) => s + (t.size_mb || 0), 0);
  document.getElementById('statTotalTasks').textContent = tasks.length;
  document.getElementById('statTotalFiles').textContent = totalFiles;
  document.getElementById('statTotalSize').innerHTML =
    `${totalSize.toFixed(1)}<small> MB</small>`;

  // Render cards
  const grid = document.getElementById('taskGrid');
  grid.innerHTML = '';
  for (const t of tasks) {
    grid.appendChild(buildTaskCard(t));
  }

  // Modal handlers
  document.getElementById('taskModalClose').onclick = closeTaskModal;
  document.getElementById('taskModalBackdrop').onclick = (e) => {
    if (e.target.id === 'taskModalBackdrop') closeTaskModal();
  };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTaskModal();
  });
}

/* -------------- CARD -------------- */

function buildTaskCard(t) {
  const meta = TASK_META[t.task_id] || { icon: '📊', short_zh: t.name_zh, desc: '' };
  const sample = primarySampleFor(t.task_id);
  const dlBtn = sample ? `
      <a class="task-dl-btn"
         href="data/downloads/${sample.file}"
         download
         title="下载样本 CSV (${sample.label}, ${sample.size})"
         onclick="event.stopPropagation();">
        <span class="task-dl-icon">⬇</span>
        <span class="task-dl-label">CSV</span>
      </a>
  ` : '';

  const card = document.createElement('div');
  card.className = 'ds-card';
  card.dataset.taskId = t.task_id;
  card.innerHTML = `
    <div class="ds-card-head">
      <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size: 1.6rem;">${meta.icon}</span>
        <span class="ds-id">${t.task_id}</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span class="ds-n">${t.n_patients} patients</span>
        ${dlBtn}
      </div>
    </div>
    <h4>${t.name_zh} <span class="faint" style="font-weight:400; font-size:.85rem;">— ${meta.short_zh}</span></h4>
    <p>${meta.desc}</p>
    <div class="ds-tag-row" style="margin-top: 4px;">
      <span class="ds-pill">${t.n_files} files</span>
      <span class="ds-pill">${t.n_days_per_patient} days × ${t.n_patients} patients</span>
      <span class="ds-pill">${(t.size_mb || 0).toFixed(1)} MB</span>
    </div>
  `;
  card.onclick = () => openTaskModal(t.task_id);
  return card;
}

/* -------------- MODAL -------------- */

function openTaskModal(taskId) {
  const t = TASK_CACHE && TASK_CACHE.find(x => x.task_id === taskId);
  if (!t) return;
  const meta = TASK_META[taskId] || { icon: '📊', short_zh: t.name_zh, desc: '' };

  document.getElementById('taskModalEyebrow').textContent =
    `${t.n_patients} patients · ${t.n_days_per_patient} days each · ${t.n_files} CSV files`;
  document.getElementById('taskModalTitle').innerHTML =
    `${meta.icon}&nbsp; ${t.name_zh} <span class="faint mono" style="font-size:.85rem; font-weight:400;">${t.task_id}</span>`;
  document.getElementById('taskModalSub').textContent =
    `data/synthetic/by_task/${t.task_id}/  ·  ${(t.size_mb || 0).toFixed(2)} MB`;

  const body = document.getElementById('taskModalBody');

  // Patient grid
  const allPids = ['P01','P02','P03','P04','P05','P06','P07','P08','P09','P10'];
  const inSet = new Set(t.patients || []);
  const patientCells = allPids.map(pid => {
    const present = inSet.has(pid);
    const cls = present ? 'ds-pill' : 'ds-pill';
    const opacity = present ? '1' : '0.32';
    const bg = present ? 'rgba(94,234,212,0.10)' : 'var(--bg-elev-2)';
    const color = present ? 'var(--accent)' : 'var(--text-faint)';
    const border = present ? 'rgba(94,234,212,0.30)' : 'var(--border)';
    return `<span class="${cls}" style="opacity:${opacity}; background:${bg}; color:${color}; border-color:${border}; font-family: var(--font-mono); padding: 4px 12px;">${pid}${present ? '' : ' ·skip'}</span>`;
  }).join(' ');

  // Path examples
  const ex1 = `data/synthetic/by_task/${t.task_id}/${(t.patients||[])[0] || 'P01'}_day00.csv`;
  const ex2 = `data/synthetic/by_task/${t.task_id}/${(t.patients||[])[0] || 'P01'}_day29.csv`;
  const ex3 = `data/synthetic/by_patient/${(t.patients||[])[0] || 'P01'}/sensor/day00_${t.task_id}.csv`;

  // CSV columns
  const baseCols = [
    ['timestamp', 'float (s)', '相对采样时刻 0..60'],
    ['gsr', 'int', '皮肤电导 raw (filtered 见衍生列)'],
    ['hr_bpm_avg', 'float', '心率 (PPG 提取)'],
    ['imu_ax_mps2', 'float', 'IMU x 轴加速度'],
    ['imu_ay_mps2', 'float', 'IMU y 轴加速度'],
    ['imu_az_mps2', 'float', 'IMU z 轴加速度'],
    ['svm', 'float', '合加速度强度 √(ax² + ay² + az²)'],
    ['jerk', 'float', '加速度一阶差分, 反映动作平稳度'],
    ['patient_id', 'str', `${(t.patients||[])[0] || 'P01'} ...`],
    ['day', 'int', '0..29 当前 patient 的纵向天数'],
    ['progression', 'float [0,1]', '当日 effective_progression — 跨模态共享'],
  ];

  const colsHtml = `
    <div class="ds-table-scroll">
      <table class="tbl">
        <thead><tr><th>Column</th><th>Type</th><th>说明</th></tr></thead>
        <tbody>
          ${baseCols.map(([c,t2,d]) => `<tr><td class="mono">${c}</td><td>${t2}</td><td>${d}</td></tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;

  // Download samples for this task
  const samples = SAMPLE_DOWNLOADS[taskId] || [];
  const isWalkingNormal = taskId === 'walking_normal';
  const downloadHeader = isWalkingNormal
    ? `<h4>📥 下载样本数据 CSV <span class="faint" style="font-weight:400; font-size:.85rem;">— ${samples.length} 个对比样本 (Day 0/25 + 多 patient)</span></h4>`
    : `<h4>📥 下载样本数据 CSV</h4>`;
  const downloadList = samples.length ? `
    <div class="task-dl-list">
      ${samples.map(s => `
        <a class="task-dl-row" href="data/downloads/${s.file}" download>
          <span class="task-dl-icon">⬇</span>
          <span class="task-dl-name mono">${s.file}</span>
          <span class="task-dl-meta">${s.label}</span>
          <span class="task-dl-size">${s.size}</span>
        </a>
      `).join('')}
    </div>
    <p class="muted" style="margin-top: 10px; font-size: 0.85rem; line-height: 1.55;">
      样本只取每天前 40 秒 (2000 行 @ 50Hz) 演示用. 完整 30 天 × 50Hz × 60s 数据需本地跑生成器输出.
    </p>
  ` : '<div class="muted">No sample download available for this task.</div>';

  body.innerHTML = `
    <div class="modal-section">
      <h4>Task description</h4>
      <p style="color: var(--text); margin: 0 0 6px;">${meta.desc}</p>
      <div class="ds-tag-row" style="margin-top: 8px;">
        ${(meta.column_focus || []).map(c => `<span class="ds-badge">${c}</span>`).join('')}
      </div>
    </div>

    <div class="modal-section">
      ${downloadHeader}
      ${downloadList}
    </div>

    <div class="modal-section">
      <h4>该任务覆盖的 ${t.n_patients} 个患者</h4>
      <div style="display:flex; flex-wrap:wrap; gap:8px;">${patientCells}</div>
      <p class="muted" style="margin-top: 12px; font-size: 0.9rem;">
        每个 patient 在该任务下 30 天各自生成一个 CSV.
        退化幅度因人而异 — 不同 progression pattern (linear / stepwise / plateau / fluctuation / acute_event)
        与 cognitive_reserve_factor 决定每位 patient 的退化曲线形状, 因此 P01 的 day29 与 P05 的 day29 在该任务下波形相差很大.
      </p>
    </div>

    <div class="modal-section">
      <h4>文件路径示例</h4>
      <pre class="ds-code"><code># Task-centric (VBVR-style, 推荐用于训练任务独立 Analyzer/Agent)
${ex1}
${ex2}

# Patient-centric (个体纵向, 与 EMA/量表对齐)
${ex3}</code></pre>
    </div>

    <div class="modal-section">
      <h4>CSV 列结构 (50Hz × 60s = 3000 行)</h4>
      ${colsHtml}
    </div>

    <div class="modal-section">
      <h4>VBVR alignment</h4>
      <div class="ds-howuse">
        每个 task 的 <span class="mono">by_task/${t.task_id}/</span> 目录下 ${t.n_files} 个 CSV 可作为该任务独立的训练集
        — 与 VBVR 项目 M-002 / M-003 各自独立 pipeline 的结构一致.
        <br />Analyzer 可以单独学 "${t.name_zh}" 任务下的退化模式, 而不被其他任务干扰.
      </div>
    </div>
  `;

  document.getElementById('taskModalBackdrop').classList.add('open');
}

function closeTaskModal() {
  document.getElementById('taskModalBackdrop').classList.remove('open');
}
