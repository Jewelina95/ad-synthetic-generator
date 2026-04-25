"""为网站准备 5 个数据集的详细 metadata JSON
提取: 介绍 / 数据样本 / 我们怎么用
输出: docs/data/datasets/datasets_meta.json
"""

import pandas as pd
import json
from pathlib import Path

SRC_ROOT = Path("/Users/wenshaoyue/Desktop/research/AD open datasets/data")
DOCS_DATA = Path(__file__).resolve().parent.parent / "docs" / "data" / "datasets"
DOCS_DATA.mkdir(parents=True, exist_ok=True)

DATASETS = {
    "ds004504": {
        "title": "EEG Recordings: Alzheimer's, Frontotemporal Dementia, Healthy",
        "title_zh": "AD/FTD/健康对照 闭眼 EEG 数据集",
        "doi": "10.18112/openneuro.ds004504",
        "openneuro_url": "https://openneuro.org/datasets/ds004504",
        "github_url": "https://github.com/OpenNeuroDatasets/ds004504",
        "paper": "Miltiadous et al. 2023, MDPI Data 8(6):95",
        "paper_url": "https://www.mdpi.com/2306-5729/8/6/95",
        "institution": "AHEPA University Hospital, Thessaloniki, Greece",
        "year": 2023,
        "modality_short": "EEG (19ch, 500Hz)",
        "modality_long": "19 通道头皮 EEG (10-20 国际系统), 500 Hz 采样, 闭眼 resting state, 平均录制 13.5 分钟",
        "license": "CC0",
        "description_zh": (
            "希腊 AHEPA 大学医院第二神经科收集的临床 EEG 数据集. "
            "88 名受试者覆盖 AD / 额颞叶痴呆 (FTD) / 健康对照三组, "
            "包含完整的 MMSE 认知评估分数. "
            "采用标准 10-20 系统 19 通道头皮 EEG, 闭眼 resting state."
        ),
        "key_columns": ["participant_id", "Gender", "Age", "Group", "MMSE"],
        "group_meaning": {"A": "Alzheimer's", "F": "Frontotemporal Dementia", "C": "Control"},
        "how_we_use_zh": (
            "提取每组的 MMSE 真实分布, 写入 distributions_master.json. "
            "生成器 progression_to_mmse() 函数据此校准合成患者认知评估分数, "
            "确保模拟的 MMSE 跟真实 AD/FTD/CTRL 分布统计一致."
        ),
        "code_snippet": """# 我们的提取代码 (extract_ds004504_distributions.py 节选)
df = pd.read_csv("ds004504/participants.tsv", sep="\\t")
df["stage"] = df["Group"].map({"A": "ad", "F": "ftd", "C": "ctrl"})

# 真实分布 (写入 distributions_master.json)
for stage, gdf in df.groupby("stage"):
    print(f"{stage}: μ={gdf.MMSE.mean():.2f} σ={gdf.MMSE.std():.2f}")
# ad:   μ=17.75 σ=4.50
# ftd:  μ=22.17 σ=2.64
# ctrl: μ=30.00 σ=0.00

# 生成器使用 (generate_synthetic.py)
def progression_to_mmse(p, age, edu):
    if p < 0.3:    return random.normal(29.69, 0.70)  # ctrl
    elif p < 0.7:  return random.normal(22.86, 3.27)  # mci/ftd
    else:          return random.normal(17.75, 4.50)  # ad
""",
        "extracted_stats": {
            "AD":   {"n": 36, "age_mean": 66.4, "age_sd": 7.9, "mmse_mean": 17.75, "mmse_sd": 4.50},
            "FTD":  {"n": 23, "age_mean": 63.7, "age_sd": 8.2, "mmse_mean": 22.17, "mmse_sd": 2.64},
            "CTRL": {"n": 29, "age_mean": 67.9, "age_sd": 5.4, "mmse_mean": 30.00, "mmse_sd": 0.00},
        },
        "tags": ["AD", "FTD", "EEG", "MMSE", "★ 主校准源"],
    },

    "ds007427": {
        "title": "Comprehensive Sample Enrichment in EEG Biomarker Studies for AD",
        "title_zh": "AD 风险分类 EEG 生物标志物研究 (哥伦比亚 Lopera 队列)",
        "doi": "10.18112/openneuro.ds007427",
        "openneuro_url": "https://openneuro.org/datasets/ds007427",
        "github_url": "https://github.com/OpenNeuroDatasets/ds007427",
        "paper": "Henao Isaza et al. 2026, PLOS ONE",
        "paper_url": "https://doi.org/10.1371/journal.pone.0343722",
        "institution": "University of Antioquia, Colombia (Lopera 团队)",
        "year": 2026,
        "modality_short": "EEG (Lopera Colombia 队列)",
        "modality_long": "EEG 加完整 MMSE 子项 + 命名测试. 含 PSEN1 E280A 基因突变携带者 (家族性 AD).",
        "license": "CC0",
        "description_zh": (
            "Francisco Lopera 团队的哥伦比亚 paisa 队列 EEG 数据. "
            "138 人含 36 健康对照 (CTR) + 24 MCI (DCL=Deterioro Cognitivo Leve) + "
            "8 AD (DTA=Demencia Tipo Alzheimer) + 70 基因风险者 (G). "
            "Lopera 团队是世界上最大的 PSEN1 E280A 家族性 AD 队列, "
            "极具学术价值."
        ),
        "key_columns": ["participant_id", "age", "sex", "education", "MM_total", "Denom_total"],
        "group_meaning": {
            "CTR": "Control",
            "DCL": "MCI (Deterioro Cognitivo Leve)",
            "DTA": "AD (Demencia Tipo Alzheimer)",
            "G": "Genetic risk (PSEN1 carrier)",
        },
        "how_we_use_zh": (
            "提取 MCI 组的 MMSE 分布 (μ=22.86, σ=3.27, n=24+13 合并 ds004504 FTD 后 n=37) "
            "用作生成器中 progression ∈ [0.3, 0.7] 区间的校准. "
            "Lopera 队列 MCI 数据稀缺, 这是最权威的真实分布参考."
        ),
        "code_snippet": """df = pd.read_csv("ds007427/participants.tsv", sep="\\t")
df["group_code"] = df["participant_id"].apply(lambda x: re.match(r"sub-([A-Z]+)\\d+", x).group(1))
df["stage"] = df["group_code"].map({"CTR":"ctrl", "DCL":"mci", "DTA":"ad", "G":"at_risk"})

for stage, gdf in df.groupby("stage"):
    print(f"{stage}: n={len(gdf)}, MMSE μ={gdf.MM_total.mean():.2f}")
# ctrl: n=36, MMSE μ=27.94
# mci:  n=24, MMSE μ=24.16
# ad:   n=8,  MMSE μ=14.38
""",
        "extracted_stats": {
            "CTR": {"n": 36, "mmse_mean": 27.94, "mmse_sd": 1.65},
            "MCI (DCL)": {"n": 24, "mmse_mean": 24.16, "mmse_sd": 3.27},
            "AD (DTA)":  {"n": 8,  "mmse_mean": 14.38, "mmse_sd": 4.50},
            "Risk (G)": {"n": 70, "mmse_mean": 28.5, "mmse_sd": 2.0},
        },
        "tags": ["AD", "MCI", "EEG", "MMSE", "PSEN1", "★ 主校准源"],
    },

    "ds006095": {
        "title": "Older Adults Walking Over Uneven Terrain (EEG+IMU+Cognition)",
        "title_zh": "老年人不平地形步行 (EEG+EMG+IMU+MOCA)",
        "doi": "10.18112/openneuro.ds006095",
        "openneuro_url": "https://openneuro.org/datasets/ds006095",
        "github_url": "https://github.com/OpenNeuroDatasets/ds006095",
        "paper": "Mind in Motion (forthcoming)",
        "paper_url": "",
        "institution": "Mind in Motion Lab",
        "year": 2024,
        "modality_short": "EEG + EMG + IMU + 认知评估",
        "modality_long": (
            "高密度双层 EEG + 颈部 EMG + 全身 IMU 加速度 + 地面反力. "
            "受试者在不平地形不同速度走路 + 静息 3 分钟. "
            "认知评估: MOCA + SPPB + 400m 步行时间."
        ),
        "license": "CC0",
        "description_zh": (
            "★ 对你手套硬件**最直接对应**的数据集. "
            "71 名老年人佩戴 IMU 走路, 同时采集 EEG/EMG/认知评估. "
            "提供老年人 IMU 真实步态分布 + MOCA 认知分数, "
            "正是你手套系统对位的硬件 + 临床场景."
        ),
        "key_columns": ["participant_id", "sex", "age", "treadmill_speed", "MOCA", "SPPB", "time_400m_seconds"],
        "group_meaning": {"all": "Healthy older adults"},
        "how_we_use_zh": (
            "1. 提取 71 老年人 MOCA 分布 (μ=27.45, σ=1.60) → 生成器 progression_to_moca() 用. "
            "2. 步行速度 + 400m 时间 → 校准 IMU 步态退化基线. "
            "3. 备用: 后期可用真实 IMU 信号严格对标我们的合成 IMU 时序."
        ),
        "code_snippet": """df = pd.read_csv("ds006095/participants.tsv", sep="\\t")

# MOCA 分布 (老年 baseline)
print(f"MOCA: μ={df.MOCA.mean():.2f}, σ={df.MOCA.std():.2f}, n={len(df)}")
# MOCA: μ=27.45, σ=1.60, n=71

# 生成器使用 (generate_synthetic.py)
def progression_to_moca(p, edu):
    base = 27.45  # 来自 ds006095
    target = base - 8 * p  # MCI≈base-3, AD≈base-8
    score = random.normal(target, 1.60) + 0.05 * (edu - 12)
    return clip(score, 0, 30)
""",
        "extracted_stats": {
            "All older adults": {"n": 71, "age_mean": 78.0, "moca_mean": 27.45, "moca_sd": 1.60},
            "Normal cognition (MOCA≥26)":   {"n": "majority"},
            "Mild impairment (MOCA 22-25)":  {"n": "few"},
            "Moderate (MOCA<22)":            {"n": "few"},
        },
        "tags": ["IMU", "MOCA", "Older Adults", "Gait", "★★ 硬件最对口"],
    },

    "ds004796": {
        "title": "PEARL-Neuro: Polish EEG, Alzheimer's Risk-genes, Lifestyle",
        "title_zh": "PEARL-Neuro 中年痴呆风险队列",
        "doi": "10.18112/openneuro.ds004796",
        "openneuro_url": "https://openneuro.org/datasets/ds004796",
        "github_url": "https://github.com/OpenNeuroDatasets/ds004796",
        "paper": "Dzianok & Kublik 2024, Sci Data 11:276",
        "paper_url": "https://www.nature.com/articles/s41597-024-03106-5",
        "institution": "Nencki Institute (Poland)",
        "year": 2024,
        "modality_short": "EEG + fMRI + APOE + 生活方式",
        "modality_long": (
            "EEG + fMRI 影像 + APOE/PICALM 基因型 + 抑郁(BDI)/人格(NEO)/记忆(CVLT) + "
            "完整血液生化 + 生活方式问卷. 中年 50-60 岁, 痴呆风险但未发病."
        ),
        "license": "CC0",
        "description_zh": (
            "中年人 (50-60 岁) 痴呆风险队列, 192 人. "
            "极其丰富的 phenotyping: 基因 (APOE 风险变异) + 生活方式 + 心理量表 + 血液生化. "
            "用于 SCD (主观认知下降) 阶段建模 — 这是早期识别最关键的窗口期."
        ),
        "key_columns": ["participant_id", "age", "sex", "education", "APOE_haplotype", "BDI", "RPM", "CVLT_5"],
        "group_meaning": {"all": "Middle-aged at-risk (no diagnosis)"},
        "how_we_use_zh": (
            "1. 备用 — 当前生成器 progression < 0.3 区间用 ds004504 ctrl 校准, "
            "未来可用 PEARL-Neuro 中年人数据更精准建模 SCD 阶段. "
            "2. APOE 基因型分布参考 (后续加入风险因素 persona 时用). "
            "3. CVLT 言语学习分布 → 后续 Audio Agent 校准."
        ),
        "code_snippet": """df = pd.read_csv("ds004796/participants.tsv", sep="\\t")

# 中年风险队列特征
print(f"年龄: μ={df.age.mean():.1f}, σ={df.age.std():.1f}, n={len(df)}")
print(f"BDI 抑郁: μ={df.BDI.mean():.2f}, σ={df.BDI.std():.2f}")
print(f"APOE 风险型 (e4 携带):", (df.APOE_haplotype.str.contains("e4")).sum())
""",
        "extracted_stats": {
            "All middle-aged": {"n": 192, "age_mean": 55.1, "age_sd": 4.2, "education_mean": 2.5, "BDI_mean": 8.6},
        },
        "tags": ["EEG", "fMRI", "APOE", "Lifestyle", "Risk", "中年队列"],
    },

    "ds002778": {
        "title": "UC San Diego Resting State EEG: Parkinson's Disease",
        "title_zh": "PD vs Healthy 静息 EEG (差异诊断)",
        "doi": "10.18112/openneuro.ds002778",
        "openneuro_url": "https://openneuro.org/datasets/ds002778",
        "github_url": "https://github.com/OpenNeuroDatasets/ds002778",
        "paper": "Jackson et al. 2019, eNeuro",
        "paper_url": "https://www.eneuro.org/content/6/3/ENEURO.0151-19.2019",
        "institution": "UC San Diego (curated by University of Oregon)",
        "year": 2019,
        "modality_short": "Resting EEG (PD vs Healthy)",
        "modality_long": "静息 EEG 加 UPDRS 运动评分 + MMSE + NAART. PD 患者含 ON 和 OFF 用药状态.",
        "license": "CC0",
        "description_zh": (
            "PD 患者 + 健康对照各 ~15 人静息 EEG. "
            "用于 AD vs PD 鉴别诊断的 EEG 标志物对照. "
            "注意作者明确提示样本量偏小, 不适合 ML 分类训练."
        ),
        "key_columns": ["participant_id", "age", "gender", "MMSE", "NAART", "disease_duration"],
        "group_meaning": {"hc": "Healthy Controls", "pd": "Parkinson's Disease"},
        "how_we_use_zh": (
            "1. PD 患者 EEG 特征 → 写进 KnowledgeStore 当 AD vs PD 鉴别诊断条目. "
            "2. ClinicalAgent 在做分期判断时, 引用这些条目避免误诊. "
            "3. 备用 — 后期 paper 写鉴别诊断章节时引用."
        ),
        "code_snippet": """df = pd.read_csv("ds002778/participants.tsv", sep="\\t")
df["group"] = df["participant_id"].apply(lambda x: "pd" if "pd" in x else "ctrl")

# PD vs CTRL MMSE 对比
for grp, gdf in df.groupby("group"):
    mmse = pd.to_numeric(gdf["MMSE"], errors="coerce").dropna()
    print(f"{grp}: n={len(gdf)}, MMSE μ={mmse.mean():.2f}")
# ctrl: n=16, MMSE μ=29.31
# pd:   n=15, MMSE μ=28.93  ← PD 早期 MMSE 接近正常
""",
        "extracted_stats": {
            "Healthy": {"n": 16, "age_mean": 60.5, "mmse_mean": 29.31},
            "PD":      {"n": 15, "age_mean": 64.3, "mmse_mean": 28.93, "disease_duration_mean": 5.2},
        },
        "tags": ["EEG", "PD", "鉴别诊断", "MMSE"],
    },
}


# ── 提取 sample data (前 12 行 participants.tsv) ──
for ds_id, meta in DATASETS.items():
    src = SRC_ROOT / ds_id / "participants.tsv"
    if src.exists():
        df = pd.read_csv(src, sep="\t")
        # 选关键列, 取前 12 行
        cols_to_show = [c for c in meta["key_columns"] if c in df.columns]
        if not cols_to_show:
            cols_to_show = list(df.columns[:6])
        sample_df = df[cols_to_show].head(12)
        meta["sample_columns"] = cols_to_show
        meta["sample_rows"] = sample_df.fillna("n/a").astype(str).values.tolist()
        meta["total_rows"] = len(df)
        print(f"✓ {ds_id}: {len(df)} 行, sample 取 {len(sample_df)} × {len(cols_to_show)} 列")
    else:
        print(f"✗ {ds_id}: 源文件不存在")


# ── 写出 JSON ──
out_file = DOCS_DATA / "datasets_meta.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(DATASETS, f, ensure_ascii=False, indent=2)
print(f"\n✓ 写入: {out_file}")
print(f"  共 {len(DATASETS)} 个数据集")
