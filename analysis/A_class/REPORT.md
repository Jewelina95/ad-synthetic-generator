# A 类同人多模态数据集分析报告
**日期**: 2026-05-01
**承接**: B 类 EEG 报告 (`analysis/REPORT.md`) 中发现的 jerk-MMSE 跨模态脱钩 bug
**核心使命**: 用 PPG+IMU 同人真实数据回答 4 个研究问题，量化 B 类 generator 的偏差，并给出修复方案
**数据**: WESAD (n=15) + PPG-DaLiA (n=15) + mHealth (n=10) + PAMAP2 (n=9) = **n=49 真同人多模态受试者**

---

## 一句话结论

**B 类 generator 的 walking_normal 任务与真实 walking 之间的 KS 距离 = 0.94 (HR), 0.75 (jerk)，跨模态耦合 ρ=0.13 vs 真实 0.51——bug 实锤，必须修。**

---

## 关键数字

- **5024 个 60 秒滑窗** 来自 48 个有效受试者（PAMAP2 1 个受试者无 walking 标签被剔除）
- **42 小时同人 PPG+IMU 数据**（WESAD+PPG-DaLiA 合计，30 受试者，是 generator fine-tune 的训练集核心）
- **跨数据集 jerk↔HR 法则**: HR_BPM = 71.4 + 4.06 × log(1 + jerk_std), r=0.38, p<1e-169
- **per-dataset 跨模态耦合 ρ**: PAMAP2 0.75 / mHealth 0.64 / DaLiA 0.52 / WESAD 0.26 — 真实数据普遍 ρ>0.5（活动队列），WESAD 弱因为 stress 是"高 HR 低 jerk"模式
- **B 类 generator 当前 ρ=0.13**，gap 0.38

---

## 4 个研究方向的回答

### Q1. 用 4 个数据集 feature 改进 generator

**Activity → HR/jerk 的真实查表 (LUT, 写入 `features/activity_hr_lut.csv`)**

| 活动桶 | WESAD HR | DaLiA HR | mHealth HR | PAMAP2 HR | 共识 |
|---|---|---|---|---|---|
| rest | 71.7 | 76.4 | 74.2 | 80.6 | **75 ± 4** |
| walking | — | 83.6 | 91.5 | 112.8 | **96 ± 15** |
| stairs | — | 87.8 | 120.6 | 129.6 | **113 ± 22** |
| stress (TSST) | 78.5 | — | — | — | **78** (HR↑无 jerk↑) |
| vigorous | — | — | 117 | 160 | **140 ± 30** |

**bug 1（generator walking）**: 当前 generator walking_normal 的 HR 只有 66 BPM (静止水平)，应改为 **96 ± 15 BPM**。
**bug 2（generator stress 缺失）**: generator 没有"情绪激发但身体不动"的模式 (HR↑ + jerk 低)，BPSD 焦虑/激越 episode 应使用 WESAD stress 模板。

### Q2. Transformer 数据规模审计

| 数据资产 | 数量 |
|---|---|
| 同人 PPG+IMU 配对小时数 | **~42 小时**（WESAD 15.6 h + DaLiA 26.7 h）|
| 总活动类别数（去重） | **~22 种**（rest/walking/stairs/cycling/running/stress/...）|
| 同人 IMU+HR 总小时数 | **~50 小时**（加上 PAMAP2 7 h + mHealth 0.7 h）|

**结论**：
- ❌ 从零训 Transformer time-series 模型不够（最少需 1000+ 小时）
- ✅ 预训练 → fine-tune 路线可行（Chronos, Moirai, Lag-Llama 这类基础模型 fine-tune 只需 10-100 小时）
- ✅ Conditional Diffusion-Transformer (CM-DiT，B 类报告推荐架构) 用 42 小时做 PoC 够

**推荐技术栈**: BioDiffusion (ECG/EEG 已有开源) → 改 BVP 通道 → 加 IMU contrastive head

### Q3. Claude 生成 vs 真实——超越/不足在哪

| 维度 | B 类 generator | 真实 (A 类) | 评价 |
|---|---|---|---|
| 跨模态耦合 ρ(jerk, HR) | 0.13 | 0.51 | ❌ 重大缺陷 |
| walking HR 均值 | 66 BPM | 94 BPM | ❌ 偏低 28 BPM |
| walking HR 标准差 | 4.7 | 18.2 | ❌ 多样性几乎为零 |
| walking jerk 均值 | 101 | 63 | ❌ 偏高 60% |
| HR 分布 KS 距离 | — | — | 0.94 (基本不重叠) |
| jerk 分布 KS 距离 | — | — | 0.75 |
| BPSD 注入 | 90% 患病率 + 5 episode | NPI 量表 + 李医生采访校准 | ✅ 比真实数据集更全 |
| 个体异质性（personas）| 5 progression × 5 reserve | 不可控 | ✅ 真实数据没有 |
| 临床合理性（progression）| 30 天纵向 + 教育调节 | 横截面单点 | ✅ 真实数据没有 |

**Claude generator 真正"超越"真实数据的部分**：纵向轨迹 + persona 可控 + BPSD 时序注入。这三件事真实数据集都做不到（全是横截面/单点）。

**Claude generator 不及真实的部分**：信号层（HR/jerk 数值 + 跨模态耦合）。这是必须修的。

### Q4. 数据呈现 + 评估超越 accuracy

A 类数据揭示的"突破性可视化"3 件套：

1. **跨数据集 activity manifold** (`fig3_subject_manifold.png`)
   - x=jerk (log), y=HR, color=activity bucket
   - 一眼看出 4 个数据集占据不同 manifold 区域
   - generator 应该被 overlay 在这 4 个 manifold 上看是否落入"真实人群可达区域"

2. **跨模态耦合强度 bar chart** (`fig2_jerk_hr_coupling.png`)
   - 直接显示 generator ρ=0.13 落在真实数据 ρ=0.26-0.75 区间外
   - 比单独一个 KS 检验数字直观 100 倍

3. **HR/jerk 双 KS 距离热图**（待开发）
   - generator 每个 patient × 每个 task 一个格子
   - 颜色 = KS 距离，标黄色 = ks_p<0.05 失真区域
   - 单个数字盲区 → 矩阵高亮

**FUPCC 框架（B 类提出）的 A 类填充**：

| 维度 | A 类提供的具体指标 |
|---|---|
| **F**idelity | 跨模态耦合 ρ_gap、活动→HR LUT 距离、KS HR/jerk |
| **U**tility | 用合成数据训分类器，在真实 A 类 walking-vs-rest 上的 AUC |
| **P**rivacy | 最近邻距离 NN-DCR vs 训练集（A 类 49 受试者）|
| **P**lausibility | 6 临床/HCI 专家盲评 generator 的 walking 波形是否"看起来对" |
| **C**overage | A 类活动 manifold 的覆盖率 (precision/recall vs real) |

---

## 重大发现汇总

### 发现 1：真实数据 jerk↔HR 是强耦合 (ρ=0.51)，generator 是脱钩 (ρ=0.13)

per-subject Spearman ρ 在 4 个数据集分别是 0.29, 0.51, 0.67, 0.76 — 越接近"日常活动"队列耦合越强。这是 generator 必须修的第一件事。

### 发现 2：generator 把 walking 的 HR 设成静止水平

walking 期望 94±18 BPM，generator 给的是 66±5 BPM。这意味着：
- generator 没有"活动激发心率"机制
- 病程退化引起的"活动后 HR 反应钝化"无法建模
- 临床医生看一眼就会发现假

### 发现 3：WESAD stress 是真实数据中独特的"高 HR 低 jerk"模式
HR 78.5 + jerk 128 (vs walking jerk 200+, HR 84) — 这是 generator 没有的 BPSD/焦虑模板。

### 发现 4：4 个数据集设备/位置量级差异巨大，必须 z-score 归一化
PAMAP2 hand acc16g jerk = 467（vigorous）, DaLiA Empatica E4 wrist = 14。这意味着：
- 不能直接合并训练 Transformer
- Per-dataset normalization 是必须步骤
- 生成器输出也要 condition on "device/position" 才能可移植

### 发现 5：42 小时同人多模态够 fine-tune，不够从零训

---

## 给 B 类 generator 的具体修复 patch

`/Users/wenshaoyue/Desktop/research/AD generator/src/generate_synthetic.py` 修改清单：

```python
# 1. 修复 walking HR 基线
WALKING_HR_BASE = 94      # was hardcoded ~66
WALKING_HR_STD = 18       # was ~5

# 2. 实施跨模态耦合 (A 类法则)
def derive_hr_from_jerk(jerk_std_window, age, mmse, base_offset):
    """HR_BPM = 71.4 + 4.06 * log(1+jerk_std) + age_drift + mmse_drift"""
    base = 71.4 + 4.06 * np.log1p(jerk_std_window)
    age_term = (age - 65) * 0.3      # 老化心率代偿不足
    mmse_term = (30 - mmse) * 0.5    # AD 心率反应钝化（待 ADNI 校准）
    return base + age_term - mmse_term + base_offset

# 3. 注入 stress mode (HR↑ jerk 不变)
def inject_bpsd_anxiety_episode(hr_series, jerk_series, prob=0.05):
    """从 WESAD stress 模板：HR baseline + 8 BPM, jerk 不变, 5-15 min"""
    ...
```

---

## 输出文件清单

```
analysis/A_class/
├── REPORT.md                                ← 本文件
├── scripts/
│   ├── 00_probe_structure.py
│   ├── 01_extract_features_wesad_dalia.py   (5024 windows 抽取核心)
│   ├── 02_extract_features_mhealth_pamap2.py
│   ├── 03_cross_dataset_analysis.py         (4 个研究问题答案)
│   └── 04_eval_generator_vs_real.py         (Generator vs Real)
├── features/
│   ├── dataset_structure.json
│   ├── wesad_features.csv     (1406 行)
│   ├── dalia_features.csv     (3015 行)
│   ├── mhealth_features.csv   (91 行)
│   ├── pamap2_features.csv    (512 行)
│   ├── activity_hr_lut.csv    (★ generator 直接用)
│   ├── jerk_hr_coupling.csv
│   ├── A_class_summary.json   (一致汇总)
│   └── eval_generator_vs_real.json  (★ bug 实锤报告)
└── figures/
    ├── fig1_activity_hr_jerk.png      (跨数据集 activity → HR/jerk)
    ├── fig2_jerk_hr_coupling.png      (跨模态耦合强度)
    ├── fig3_subject_manifold.png      (4 数据集 manifold)
    └── fig4_gen_vs_real.png           (★ bug 可视化)
```

---

## 下一步建议（优先级）

1. **修 generator HR 基线 + 跨模态耦合**（1-2 天）—— 用 `activity_hr_lut.csv` + 上面的 `derive_hr_from_jerk()` 函数；预期把 ρ 从 0.13 推到 0.40+，KS HR 从 0.94 降到 0.3-
2. **加 BPSD anxiety/stress 模板**（1-2 天）—— 用 WESAD stress 段直接当 prototype
3. **PoC：BioDiffusion 改 BVP+IMU 双通道 fine-tune on WESAD+DaLiA**（1 周）—— 看 unconditional 生成是否落进真实 manifold
4. **加入条件**（age, MMSE, persona, activity, device）→ CM-DiT 第一个版本（2-3 周）
5. **临床医生盲评**（plausibility 评估的金标准，FUPCC 第 4 维）

---

**END · 2026-05-01 · A class analysis**
