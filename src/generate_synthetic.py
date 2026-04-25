"""生成器 v2 — 用真实数据集分布校准 (含 BPSD/缺失/认知储备)
基于:
  - 真实健康 baseline (data/baseline 4.8/cleaned/S0X_*_cleaned.csv)
  - 真实分布 (AD open datasets/output/distributions_master.json, n=112)
  - 文献效应量 (剪切/HRV/EDA 退化系数)

v2 新增 (vs v1):
  ★ 纵向轨迹 (天数可配)
  ★ 5 种进展模式 + Persona 多样性
  ★ MMSE/MoCA 真实分布对标
  ★ EMA + 周量表 + 月度 note
  ★ 跨模态从同一 progression 派生 (sensor/EMA/量表/note 同步)

v2.1 新增:
  ⭐ BPSD episode 突发事件注入 (激越/日落/游荡)
  ⭐ 缺失数据 + 运动伪迹模拟 (患者忘充电/撕扯传感器)
  ⭐ 认知储备 (高教育者掩盖早期症状)
  ⭐ --days / --patients 命令行参数
"""

import sys, json, os, argparse
from pathlib import Path
import numpy as np
import pandas as pd

# ── 路径 (自包含: 项目根目录 = src 父目录) ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = PROJECT_ROOT / "data" / "baseline" / "cleaned"
DISTRIBUTIONS = PROJECT_ROOT / "data" / "distributions" / "distributions_master.json"
OUT_DIR = PROJECT_ROOT / "data" / "synthetic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 加载真实分布 ──
with open(DISTRIBUTIONS) as f:
    DIST = json.load(f)

MMSE_DIST = DIST["combined_mmse_distribution"]
MOCA_DIST = DIST["datasets"]["ds006095"]["all_subjects_aggregated"]["moca"]

# ── 退化系数 ──
DEGRADATION = {
    "imu": {
        "svm_std_factor":   lambda p: 1 + 0.5*p,
        "jerk_std_factor":  lambda p: 1 + 0.7*p,
        "speed_factor":     lambda p: 1 - 0.15*p,
    },
    "ppg": {
        "hr_std_factor":    lambda p: 1 - 0.3*p,
        "hr_mean_shift":    lambda p: 3 * p,
    },
    "eda": {
        "gsr_mean_factor":  lambda p: 1 - 0.2*p,
        "gsr_cv_factor":    lambda p: 1 + 0.4*p,
    },
}

# ── ⭐ BPSD episode 类型 ──
BPSD_TYPES = {
    "agitation": {
        "trigger_progression_min": 0.4,  # MCI/mild 才容易出
        "duration_minutes": 30,
        "effects": {
            "hr_spike": 25,           # HR 飙升 +25 bpm
            "eda_spike": 800,         # EDA 飙升 (μS 单位)
            "imu_jerk_x3": True,      # 运动剧烈
            "ema_anxiety": 9,         # 当日 anxiety 飙到 9-10
        },
    },
    "sundowning": {
        "trigger_progression_min": 0.5,
        "duration_minutes": 90,
        "time_window": (16, 18),     # 下午 4-6 点
        "effects": {
            "hr_spike": 15,
            "eda_spike": 400,
            "ema_anxiety": 7,
            "ema_mood": 3,           # mood 跌
        },
    },
    "wandering": {
        "trigger_progression_min": 0.6,
        "duration_minutes": 45,
        "effects": {
            "imu_steps_x2": True,
            "hr_mild_spike": 10,
        },
    },
}

# ── ⭐ 缺失/伪迹率 (随 progression 增) ──
def missingness_rate(progression):
    """progression 越高, 越容易忘充电/撕传感器"""
    return 0.05 + 0.20 * progression  # 5% → 25%

def artifact_rate(progression):
    return 0.03 + 0.10 * progression  # 3% → 13%

# ── ⭐ 认知储备 (高教育掩盖早期症状) ──
def cognitive_reserve_factor(education_years):
    """edu 高的人有更强 reserve, progression 在临床上表现得弱
    返回 effective_progression 的乘子, [0.6, 1.2]
    """
    if education_years >= 16:    return 0.65   # 大学+, 强 reserve
    elif education_years >= 12:  return 0.85   # 高中, 中等
    elif education_years >= 9:   return 1.00   # 初中, 平均
    elif education_years >= 6:   return 1.15   # 小学, 弱
    else:                        return 1.25   # 文盲, 最弱

# ── Persona 进展模式 ──
PROGRESSION_PATTERNS = {
    "linear":      lambda d, n: d / n,
    "stepwise":    lambda d, n: 0.0 if d < n*0.45 else 0.5 if d < n*0.7 else 0.8,
    "plateau":     lambda d, n: min(d / (n*0.25), 0.4),
    "fluctuation": lambda d, n: max(0, 0.3 + 0.2*np.sin(d/3)),
    "acute_event": lambda d, n: 0.05 if d < n*0.66 else 0.7,
}

PERSONAS = [
    {"id": "P01", "base": "S01_zewei",  "age": 68, "gender": "M", "education": 12, "pattern": "linear",      "bpsd_prone": False},
    {"id": "P02", "base": "S01_zewei",  "age": 73, "gender": "M", "education": 6,  "pattern": "stepwise",    "bpsd_prone": True},
    {"id": "P03", "base": "S02_junkai", "age": 70, "gender": "M", "education": 16, "pattern": "plateau",     "bpsd_prone": False},
    {"id": "P04", "base": "S03_jialu",  "age": 75, "gender": "F", "education": 9,  "pattern": "fluctuation", "bpsd_prone": True},
    {"id": "P05", "base": "S04_zhe",    "age": 72, "gender": "M", "education": 12, "pattern": "acute_event", "bpsd_prone": False},
    {"id": "P06", "base": "S02_junkai", "age": 65, "gender": "M", "education": 9,  "pattern": "linear",      "bpsd_prone": False},
    {"id": "P07", "base": "S03_jialu",  "age": 78, "gender": "F", "education": 6,  "pattern": "stepwise",    "bpsd_prone": True},
    {"id": "P08", "base": "S04_zhe",    "age": 71, "gender": "M", "education": 16, "pattern": "fluctuation", "bpsd_prone": False},
    {"id": "P09", "base": "S01_zewei",  "age": 76, "gender": "M", "education": 4,  "pattern": "acute_event", "bpsd_prone": True},
    {"id": "P10", "base": "S03_jialu",  "age": 69, "gender": "F", "education": 12, "pattern": "plateau",     "bpsd_prone": False},
]

# ── ⭐ 任务清单 (与 baseline 对齐) ──
# 每个任务 = 一个独立的"数据 pipeline" (类比 VBVR M-XXX 任务)
# 10 个 patient 在同一 task 下生成 10 个不同 CSV
TASKS = [
    {"id": "walking_normal",     "name_zh": "正常行走",       "n_subjects_baseline": 4},
    {"id": "walking_dual_task",  "name_zh": "双任务行走",     "n_subjects_baseline": 4},
    {"id": "balance_standing",   "name_zh": "站立平衡",       "n_subjects_baseline": 4},
    {"id": "hand_fine_motor",    "name_zh": "手部精细运动",   "n_subjects_baseline": 3},
    {"id": "sit_to_stand",       "name_zh": "坐立转换",       "n_subjects_baseline": 4},
    {"id": "turning",            "name_zh": "转身",           "n_subjects_baseline": 4},
    {"id": "wandering_simulate", "name_zh": "游荡模拟 (BPSD)", "n_subjects_baseline": 4},
]

# ── ⭐ 语音模态说明 (不合成) ──
# 我们目前**只采集了健康人的语音 baseline**, 没有 AD 患者真实语音数据.
# 因此生成器**不合成**语音特征 — 避免脱离真实分布造假.
# 语音在系统里有两个用途:
#   1. INPUT 分析: 患者实时对话 → ASR + 声学特征 → Audio Agent 推断认知状态
#   2. OUTPUT 治疗: AI 生成语音回应 → 音乐疗法/呼吸引导/认知互动 (干预闭环)
# 未来如有 AD 患者语音数据 (ADReSS / MultiConAD 中文部分), 再加入合成.
VOICE_MODALITY_NOTE = {
    "status": "not_synthesized",
    "reason": "我们只采集了健康人语音 baseline, 没有 AD 患者数据, 不能凭空合成",
    "roles_in_system": [
        {"role": "input_analysis", "desc": "ASR + 声学/语言特征 → Audio Agent 推断认知"},
        {"role": "output_therapy", "desc": "AI 语音互动 → 音乐疗法/呼吸引导/认知训练"},
    ],
    "future_data_sources": [
        "ADReSS Challenge (英文 AD 对话, 通过 DementiaBank)",
        "MultiConAD 中文部分 (TAUKADIAL / iFlytek / NCMMSC2021)",
    ],
}


def load_baselines():
    baselines = {}
    for f in BASELINE_DIR.glob("S0*_*_cleaned.csv"):
        df = pd.read_csv(f)
        subj = df["subject_id"].iloc[0] if "subject_id" in df.columns else f.stem.replace("_cleaned", "")
        if "label" not in df.columns:
            continue
        by_task = {}
        for task, gdf in df.groupby("label"):
            if pd.isna(task) or task in ["", "unknown"]:
                continue
            by_task[task] = gdf.reset_index(drop=True)
        baselines[subj] = by_task
    return baselines


# ── ⭐ BPSD episode 决策 ──
def decide_bpsd_episodes(persona, n_days, progression_fn, rng):
    """决定哪些天发生什么 BPSD"""
    episodes = []
    for day in range(n_days):
        p = progression_fn(day, n_days)
        eff_p = p * cognitive_reserve_factor(persona["education"])
        for bpsd_type, spec in BPSD_TYPES.items():
            if eff_p < spec["trigger_progression_min"]:
                continue
            # 基础概率 + bpsd_prone 加成
            base_prob = 0.05 * (eff_p - spec["trigger_progression_min"])
            if persona.get("bpsd_prone"):
                base_prob *= 2.5
            if rng.random() < base_prob:
                # 选时段 (强制转 python int, 避免 numpy int64 不能 json)
                if "time_window" in spec:
                    hour = int(rng.integers(spec["time_window"][0], spec["time_window"][1]))
                else:
                    hour = int(rng.integers(8, 22))
                episodes.append({
                    "day": int(day), "hour": hour, "type": str(bpsd_type),
                    "duration_min": int(spec["duration_minutes"]),
                    "progression_at_event": float(p),
                })
    return episodes


def degrade_sensor(baseline_df, progression, daily_seed, bpsd_today=None):
    rng = np.random.default_rng(daily_seed)
    df = baseline_df.copy()
    p = progression

    # IMU 退化
    if "imu_ax_mps2" in df.columns:
        noise_scale = 0.05 + 0.15 * p
        for col in ["imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2"]:
            df[col] = df[col] + rng.normal(0, noise_scale, len(df))
        if "svm" in df.columns:
            df["svm"] = np.sqrt(df["imu_ax_mps2"]**2 + df["imu_ay_mps2"]**2 + df["imu_az_mps2"]**2)
        if "jerk" in df.columns and "svm" in df.columns:
            df["jerk"] = df["svm"].diff().abs()

    # HR 退化
    if "hr_bpm_avg" in df.columns:
        valid = df["hr_bpm_avg"] > 0
        df.loc[valid, "hr_bpm_avg"] = (
            df.loc[valid, "hr_bpm_avg"]
            + DEGRADATION["ppg"]["hr_mean_shift"](p)
            + rng.normal(0, max(0.5, 1 - 0.3*p), valid.sum())
        ).round()

    # EDA
    if "gsr_filtered" in df.columns:
        df["gsr_filtered"] = (
            df["gsr_filtered"] * DEGRADATION["eda"]["gsr_mean_factor"](p)
            + rng.normal(0, 50 * (1 + 0.4*p), len(df))
        )

    # ⭐ BPSD 注入 (在数据中段插入一段尖峰)
    if bpsd_today:
        spec = BPSD_TYPES[bpsd_today["type"]]
        n = len(df)
        # 在数据中段 1/3 ~ 2/3 段位插入异常
        start = int(n * 0.4)
        end   = int(n * 0.6)
        if "hr_spike" in spec["effects"] and "hr_bpm_avg" in df.columns:
            df.loc[start:end, "hr_bpm_avg"] = df.loc[start:end, "hr_bpm_avg"].astype(float) + spec["effects"]["hr_spike"]
        if "hr_mild_spike" in spec["effects"] and "hr_bpm_avg" in df.columns:
            df.loc[start:end, "hr_bpm_avg"] = df.loc[start:end, "hr_bpm_avg"].astype(float) + spec["effects"]["hr_mild_spike"]
        if "eda_spike" in spec["effects"] and "gsr_filtered" in df.columns:
            df.loc[start:end, "gsr_filtered"] = df.loc[start:end, "gsr_filtered"].astype(float) + spec["effects"]["eda_spike"]
        if spec["effects"].get("imu_jerk_x3") and "jerk" in df.columns:
            df.loc[start:end, "jerk"] = df.loc[start:end, "jerk"].astype(float) * 3.0
        if spec["effects"].get("imu_steps_x2") and "imu_steps" in df.columns:
            df.loc[start:end, "imu_steps"] = df.loc[start:end, "imu_steps"].astype(float) * 2.0

    # ⭐ 缺失数据 (患者忘充电 → 整片 NaN)
    miss_rate = missingness_rate(p)
    if rng.random() < miss_rate:
        # 随机丢一段 (10-30% 长度)
        gap_frac = rng.uniform(0.10, 0.30)
        gap_len = int(len(df) * gap_frac)
        gap_start = rng.integers(0, max(1, len(df) - gap_len))
        for col in ["gsr_filtered", "ppg_ir", "hr_bpm_avg",
                    "imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2", "svm", "jerk"]:
            if col in df.columns:
                df.loc[gap_start:gap_start+gap_len, col] = np.nan

    # ⭐ 运动伪迹 (BPSD 激越时撕扯, 平时偶发)
    art_rate = artifact_rate(p)
    n_artifacts = rng.poisson(len(df) * art_rate / 100)  # 平均个数
    for _ in range(n_artifacts):
        idx = rng.integers(0, len(df))
        # 短突刺
        for col in ["imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2"]:
            if col in df.columns:
                df.loc[idx, col] = df.loc[idx, col] + rng.choice([-1, 1]) * rng.uniform(20, 50)
        if "svm" in df.columns:
            df.loc[idx, "svm"] = rng.uniform(30, 80)

    return df


def gen_ema(day, hour, p, rng, bpsd_today=None):
    base_anxiety = 2 + 5*p
    base_mood = 7 - 4*p
    # BPSD 影响 EMA
    if bpsd_today:
        spec = BPSD_TYPES[bpsd_today["type"]]
        # 同小时附近的 EMA 受影响
        if abs(hour - bpsd_today["hour"]) <= 3:
            if "ema_anxiety" in spec["effects"]:
                base_anxiety = spec["effects"]["ema_anxiety"]
            if "ema_mood" in spec["effects"]:
                base_mood = spec["effects"]["ema_mood"]
    return {
        "day": day, "hour": hour,
        "mood":          int(np.clip(rng.normal(base_mood, 1), 1, 10)),
        "sleep_quality": int(np.clip(rng.normal(7 - 3*p, 1), 1, 10)),
        "anxiety":       int(np.clip(rng.normal(base_anxiety, 1), 0, 10)),
        "energy":        int(np.clip(rng.normal(7 - 3*p, 1), 1, 10)),
        "bpsd_event":    bpsd_today["type"] if (bpsd_today and abs(hour - bpsd_today["hour"]) <= 1) else None,
    }


def progression_to_mmse(p, age, edu, rng):
    if p < 0.3:    target_mu, target_sd = MMSE_DIST["ctrl"]["mean"], MMSE_DIST["ctrl"]["sd"]
    elif p < 0.7:  target_mu, target_sd = MMSE_DIST["mci"]["mean"],  MMSE_DIST["mci"]["sd"]
    else:          target_mu, target_sd = MMSE_DIST["ad"]["mean"],   MMSE_DIST["ad"]["sd"]
    score = rng.normal(target_mu, target_sd) + 0.05 * (edu - 12)
    return float(np.clip(score, 0, 30))


def progression_to_moca(p, edu, rng):
    base = MOCA_DIST["mean"]
    target = base - 8 * p
    score = rng.normal(target, MOCA_DIST["sd"]) + 0.05 * (edu - 12)
    return float(np.clip(score, 0, 30))


def progression_to_phq9(p, rng):
    return float(np.clip(rng.normal(2 + 8*p, 2), 0, 27))


def gen_survey(day, p, persona, rng):
    return {
        "day": day,
        "mmse_estimate": round(progression_to_mmse(p, persona["age"], persona["education"], rng), 1),
        "moca_estimate": round(progression_to_moca(p, persona["education"], rng), 1),
        "phq9": round(progression_to_phq9(p, rng), 1),
    }


NOTE_TEMPLATES = {
    "stable":   "患者{age}岁{gender}，本月状态稳定。日常活动如常，认知评估在基线范围内。睡眠规律，情绪平稳。",
    "early":    "患者{age}岁{gender}，主诉近期偶有忘事。MoCA估计{moca}分（较人群均值低{drop}分）。建议家属记录日常变化，3 月后复评。",
    "moderate": "患者{age}岁{gender}，认知问题加重，MoCA估计{moca}分。家属反映出现重复提问、地点定向减弱。{bpsd_note}建议: (1) 启动认知训练; (2) 排查抑郁干预; (3) 转诊做血液 p-tau217 或 PET。",
    "severe":   "患者{age}岁{gender}，认知显著下降，MoCA估计{moca}分。出现 BPSD 症状（{bpsd_note}）。家属负担重。建议:(1) 抗 Aβ 单抗治疗评估; (2) BPSD 非药物干预 (音乐疗法); (3) 定期 ARIA 监测。",
}


def gen_note(day, p, persona, latest_survey, bpsd_episodes_so_far):
    if p < 0.2:    template = "stable"
    elif p < 0.5:  template = "early"
    elif p < 0.75: template = "moderate"
    else:          template = "severe"

    drop = round(MOCA_DIST["mean"] - latest_survey["moca_estimate"], 1)
    bpsd_note = ""
    if bpsd_episodes_so_far:
        types = set(e["type"] for e in bpsd_episodes_so_far)
        bpsd_note = f"近期发生 {', '.join(types)} 事件 {len(bpsd_episodes_so_far)} 次. "

    return {
        "day": day,
        "template": template,
        "text": NOTE_TEMPLATES[template].format(
            age=persona["age"],
            gender="男性" if persona["gender"] == "M" else "女性",
            moca=latest_survey["moca_estimate"],
            phq9=latest_survey["phq9"],
            drop=drop,
            bpsd_note=bpsd_note,
        ),
    }


def generate_one_persona(persona, baselines, n_days):
    base = baselines.get(persona["base"])
    if base is None:
        print(f"  ✗ 找不到 baseline {persona['base']}")
        return None

    progression_fn = PROGRESSION_PATTERNS[persona["pattern"]]
    cognitive_reserve = cognitive_reserve_factor(persona["education"])

    rng_master = np.random.default_rng(hash(persona["id"]) % 2**32)

    # ★ 双视图: by_patient (患者视角) + by_task (任务视角, VBVR-style)
    pdir = OUT_DIR / "by_patient" / persona["id"]
    sensor_dir = pdir / "sensor"
    sensor_dir.mkdir(parents=True, exist_ok=True)
    by_task_root = OUT_DIR / "by_task"
    by_task_root.mkdir(parents=True, exist_ok=True)

    # ⭐ BPSD 事件预先决策
    bpsd_episodes = decide_bpsd_episodes(persona, n_days, progression_fn, rng_master)

    persona_meta = {
        "patient_id": persona["id"],
        "base_subject": persona["base"],
        "age": persona["age"],
        "gender": persona["gender"],
        "education_years": persona["education"],
        "cognitive_reserve_factor": cognitive_reserve,
        "progression_pattern": persona["pattern"],
        "bpsd_prone": persona.get("bpsd_prone", False),
        "bpsd_episodes_total": len(bpsd_episodes),
        "n_days": n_days,
        "generated_with": "v2.1 (calibrated by ds004504+ds007427+ds006095, with BPSD/missing/reserve)",
    }
    with open(pdir / "persona.json", "w") as f:
        json.dump(persona_meta, f, ensure_ascii=False, indent=2)

    # 写 BPSD 事件清单
    with open(pdir / "bpsd_events.jsonl", "w") as f:
        for e in bpsd_episodes:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    progression_log = []
    ema_records = []
    survey_records = []
    note_records = []

    target_tasks = ["walking_normal", "walking_dual_task", "balance_standing", "hand_fine_motor"]
    available_tasks = [t for t in target_tasks if t in base]
    if len(available_tasks) == 0:
        print(f"  ✗ 没有可用 task in {persona['base']}")
        return None

    for day in range(n_days):
        raw_p = progression_fn(day, n_days)
        # ⭐ 认知储备修正
        eff_p = float(np.clip(raw_p * cognitive_reserve, 0, 1))
        progression_log.append({
            "day": day,
            "raw_progression": round(float(raw_p), 3),
            "effective_progression": round(eff_p, 3),
        })

        rng_day = np.random.default_rng((hash(persona["id"]) + day) % 2**32)

        # 当日 BPSD?
        bpsd_today = next((e for e in bpsd_episodes if e["day"] == day), None)

        # Sensor (每任务一段) — 同时写两份: 患者视角 + 任务视角
        for task in available_tasks:
            seed = hash((persona["id"], day, task)) % 2**32
            degraded = degrade_sensor(base[task], eff_p, daily_seed=seed, bpsd_today=bpsd_today)
            keep_cols = ["timestamp", "gsr_filtered", "ppg_ir", "hr_bpm_avg",
                         "imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2", "svm", "jerk",
                         "hr_valid_flag", "label"]
            keep_cols = [c for c in keep_cols if c in degraded.columns]
            sub = degraded[keep_cols].copy()
            sub["patient_id"] = persona["id"]
            sub["day"] = day
            sub["progression"] = round(eff_p, 3)
            # 视图 1: by_patient (个体纵向)
            sub.to_csv(sensor_dir / f"day{day:02d}_{task}.csv", index=False)
            # 视图 2: by_task (VBVR-style task-centric, 每任务一个文件夹)
            task_dir = by_task_root / task
            task_dir.mkdir(parents=True, exist_ok=True)
            sub.to_csv(task_dir / f"{persona['id']}_day{day:02d}.csv", index=False)

        # EMA
        for h in [9, 14, 20]:
            ema_records.append(gen_ema(day, h, eff_p, rng_day, bpsd_today=bpsd_today))

        # 周量表
        if day % 7 == 0:
            survey_records.append(gen_survey(day, eff_p, persona, rng_day))

        # 月度 note (Day 14, 或 if n_days < 14 用 Day 末)
        note_day = min(14, n_days - 1)
        if day == note_day and survey_records:
            past_bpsd = [e for e in bpsd_episodes if e["day"] <= day]
            note_records.append(gen_note(day, eff_p, persona, survey_records[-1], past_bpsd))

    # 写文件
    pd.DataFrame(progression_log).to_csv(pdir / "progression.csv", index=False)
    with open(pdir / "ema.jsonl", "w") as f:
        for r in ema_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(pdir / "surveys.jsonl", "w") as f:
        for r in survey_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(pdir / "notes.jsonl", "w") as f:
        for r in note_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {
        "persona": persona["id"],
        "n_days": n_days,
        "n_sensor_files": n_days * len(available_tasks),
        "n_ema": len(ema_records),
        "n_surveys": len(survey_records),
        "n_notes": len(note_records),
        "n_bpsd_events": len(bpsd_episodes),
        "tasks_used": available_tasks,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="生成多少天的轨迹")
    parser.add_argument("--patients", type=int, default=10, help="生成多少个虚拟患者 (默认 10)")
    args = parser.parse_args()

    n_days = args.days
    selected_personas = PERSONAS[:args.patients]

    # ★ 清空旧输出, 重生成 (旧结构 P01/sensor/... 已废弃, 改成 by_patient + by_task)
    import shutil
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    print("=" * 60)
    print(f"生成器 v2.1 — {n_days} 天 × {len(selected_personas)} 患者")
    print("=" * 60)
    print(f"分布参考: {DISTRIBUTIONS.name}")
    print(f"  MMSE ctrl: μ={MMSE_DIST['ctrl']['mean']:.2f} σ={MMSE_DIST['ctrl']['sd']:.2f}")
    print(f"  MMSE mci:  μ={MMSE_DIST['mci']['mean']:.2f} σ={MMSE_DIST['mci']['sd']:.2f}")
    print(f"  MMSE ad:   μ={MMSE_DIST['ad']['mean']:.2f} σ={MMSE_DIST['ad']['sd']:.2f}")
    print(f"  MOCA 老年: μ={MOCA_DIST['mean']:.2f} σ={MOCA_DIST['sd']:.2f}")
    print()

    baselines = load_baselines()
    print(f"✓ 加载 baseline: {list(baselines.keys())}")
    print()

    summary = []
    for persona in selected_personas:
        cr = cognitive_reserve_factor(persona["education"])
        print(f"生成 {persona['id']} ({persona['base']}, {persona['pattern']}, edu={persona['education']}, reserve={cr:.2f})...")
        result = generate_one_persona(persona, baselines, n_days=n_days)
        if result:
            summary.append(result)
            print(f"  ✓ {result['n_sensor_files']} sensor + {result['n_ema']} EMA + "
                  f"{result['n_surveys']} 量表 + {result['n_notes']} note + "
                  f"{result['n_bpsd_events']} BPSD 事件")
        print()

    # ★ 任务级 manifest: by_task 视图下每个 task 的统计
    by_task_root = OUT_DIR / "by_task"
    task_manifest = []
    for task_dir in sorted(by_task_root.glob("*")):
        if not task_dir.is_dir():
            continue
        task_id = task_dir.name
        files = list(task_dir.glob("*.csv"))
        # 统计该任务下患者数 + 总文件数
        patient_ids = sorted(set(f.stem.split("_day")[0] for f in files))
        task_meta = next((t for t in TASKS if t["id"] == task_id), {"name_zh": task_id})
        task_manifest.append({
            "task_id": task_id,
            "name_zh": task_meta.get("name_zh", task_id),
            "n_patients": len(patient_ids),
            "n_files": len(files),
            "n_days_per_patient": n_days,
            "patients": patient_ids,
            "total_size_mb": round(sum(f.stat().st_size for f in files) / 1024 / 1024, 2),
        })

    with open(OUT_DIR / "manifest.json", "w") as f:
        json.dump({
            "version": "v2.2",
            "n_days": n_days,
            "n_patients": len(summary),
            "n_tasks": len(task_manifest),
            "structure": {
                "by_patient": "data/synthetic/by_patient/PXX/sensor/dayXX_TASK.csv (个体纵向视图)",
                "by_task":    "data/synthetic/by_task/TASK/PXX_dayXX.csv (任务为中心, VBVR-style)",
            },
            "features": [
                "10 patients × 30-day longitudinal trajectory",
                "task-centric output (VBVR-aligned: each task has its own folder)",
                "real distribution calibration (n=112 MMSE, n=71 MOCA)",
                "cross-modal coherence (sensor/EMA/survey/note from same progression)",
                "BPSD episode injection (Lit: 90% prevalence)",
                "missing data + motion artifacts",
                "cognitive reserve adjustment",
            ],
            "voice_modality": VOICE_MODALITY_NOTE,  # ★ 语音不合成, 只标记两种用途
            "tasks": task_manifest,
            "personas": summary,
        }, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"✓ 完成. 输出: {OUT_DIR}")
    print(f"  患者: {len(summary)}, 天数: {n_days}, 任务: {len(task_manifest)}")
    print()
    print("📁 by_task 视图 (VBVR-style 任务为中心):")
    for tm in task_manifest:
        print(f"  {tm['task_id']:25s} {tm['n_patients']:3d} patients, {tm['n_files']:4d} files, {tm['total_size_mb']:.1f} MB")
    total_bpsd = sum(s['n_bpsd_events'] for s in summary)
    print(f"\n  BPSD 事件总数: {total_bpsd}")
    print()
    print("🎤 语音模态:", VOICE_MODALITY_NOTE["status"])
    print(f"   原因: {VOICE_MODALITY_NOTE['reason']}")
    print("   系统中两种用途:")
    for r in VOICE_MODALITY_NOTE["roles_in_system"]:
        print(f"     • {r['role']}: {r['desc']}")


if __name__ == "__main__":
    main()
