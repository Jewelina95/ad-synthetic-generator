"""扩展已用数据集 — 从 7 个已下载但未用的 OpenNeuro 提取更多分布
全部基于本地 participants.tsv, 不需要任何申请/等待

新增校准来源:
- ds004796 (PEARL-Neuro 192 中年): SCD/早期风险 baseline
- ds002778 (PD vs Healthy 31): 差异诊断 MMSE
- ds005363, ds005892 等: 老年/PD 对照
"""

import pandas as pd
import json
import re
from pathlib import Path

SRC = Path("/Users/wenshaoyue/Desktop/research/AD open datasets/data")
OUT = Path(__file__).resolve().parent.parent / "data" / "distributions" / "distributions_extended.json"

stats = {
    "_meta": {
        "purpose": "扩展校准 — 从 7 个已下载 OpenNeuro 数据集提取更多真实分布",
        "no_application_needed": True,
        "all_extracted_from_local_participants_tsv": True,
    },
    "datasets_used": []
}


def safe_stats(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) == 0:
        return None
    return {"n": int(len(s)), "mean": round(float(s.mean()), 2),
            "sd": round(float(s.std()), 2),
            "min": round(float(s.min()), 2), "max": round(float(s.max()), 2)}


# ============================================================
# ds004796 PEARL-Neuro (192 中年痴呆风险, 极丰富)
# ============================================================
print("\n[ds004796 PEARL-Neuro 中年风险]")
df = pd.read_csv(SRC / "ds004796" / "participants.tsv", sep="\t")
ds = {
    "id": "ds004796",
    "title": "PEARL-Neuro 中年痴呆风险队列",
    "n_total": int(len(df)),
    "use_case": "SCD/早期阶段 + 风险因素 (APOE/lifestyle) 校准",
    "extracted": {
        "age": safe_stats(df["age"]),
        "education": safe_stats(df["education"]),
        "BDI_depression": safe_stats(df["BDI"]),
        "BMI": safe_stats(df["BMI"]),
        "RPM_raven_iq": safe_stats(df["RPM"]),
        "AUDIT_alcohol": safe_stats(df["AUDIT"]),
        "CVLT_verbal_learning_5": safe_stats(df["CVLT_5"]),
    },
}
# APOE 风险型分布
if "APOE_haplotype" in df.columns:
    apoe_counts = df["APOE_haplotype"].value_counts().to_dict()
    e4_carrier = sum(v for k, v in apoe_counts.items() if isinstance(k, str) and "e4" in k)
    ds["extracted"]["apoe_distribution"] = {str(k): int(v) for k, v in apoe_counts.items()}
    ds["extracted"]["apoe_e4_carrier_rate"] = round(e4_carrier / len(df), 3)
    print(f"  APOE e4 携带率: {e4_carrier}/{len(df)} = {e4_carrier/len(df)*100:.1f}%")
print(f"  ✓ {len(df)} 中年人, age μ={df.age.mean():.1f}, BDI μ={df.BDI.mean():.1f}")
stats["datasets_used"].append(ds)


# ============================================================
# ds002778 UC San Diego PD vs Healthy
# ============================================================
print("\n[ds002778 PD vs Healthy 差异诊断]")
df = pd.read_csv(SRC / "ds002778" / "participants.tsv", sep="\t")
df["group"] = df["participant_id"].apply(lambda x: "pd" if "pd" in x else "ctrl")
ds = {
    "id": "ds002778",
    "title": "UC San Diego PD vs Healthy",
    "n_total": int(len(df)),
    "use_case": "AD vs PD 差异诊断 EEG MMSE 对照",
    "by_group": {},
}
mmse_col = next((c for c in df.columns if "MMSE" in c.upper()), None)
for grp, gdf in df.groupby("group"):
    g = {
        "n": int(len(gdf)),
        "age": safe_stats(gdf["age"]),
    }
    if mmse_col:
        g["mmse"] = safe_stats(gdf[mmse_col])
    if "disease_duration" in gdf.columns:
        g["disease_duration"] = safe_stats(gdf["disease_duration"])
    ds["by_group"][grp] = g
print(f"  ✓ ctrl n={ds['by_group'].get('ctrl', {}).get('n', 0)}, pd n={ds['by_group'].get('pd', {}).get('n', 0)}")
stats["datasets_used"].append(ds)


# ============================================================
# ds006036 (与 ds004504 同人, 不重复抽 MMSE; 标记一下)
# ============================================================
print("\n[ds006036 ds004504 姊妹版 (eyes-open + 光刺激)]")
src006036 = SRC / "ds006036" / "participants.tsv"
if src006036.exists():
    df = pd.read_csv(src006036, sep="\t")
    df.columns = [c.strip() for c in df.columns]
    ds = {
        "id": "ds006036",
        "title": "ds004504 姊妹版 (光刺激 EEG)",
        "n_total": int(len(df)),
        "use_case": "同 ds004504 88 人 patients, 不同 EEG 范式 (eyes-open + 5/10/15/30 Hz 光刺激). 双范式交叉验证用.",
        "note": "patients 完全相同 ds004504, MMSE 分布与 ds004504 一致, 不重复抽分布",
    }
    print(f"  ✓ n={len(df)} (与 ds004504 同患者)")
    stats["datasets_used"].append(ds)


# ============================================================
# ds005363 ORHA 健康老化视觉
# ============================================================
print("\n[ds005363 ORHA 健康老化视觉 EEG]")
src5363 = SRC / "ds005363" / "participants.tsv"
if src5363.exists():
    df = pd.read_csv(src5363, sep="\t")
    df.columns = [c.strip().replace("﻿", "") for c in df.columns]
    ds = {
        "id": "ds005363",
        "title": "ORHA 健康老化视觉认知 EEG",
        "n_total": int(len(df)),
        "use_case": "Y (年轻) vs O (老年) EEG 对照 — 区分'健康老化'和'AD 退化'",
        "by_group": {},
    }
    if "group" in df.columns:
        for grp, gdf in df.groupby("group"):
            ds["by_group"][str(grp)] = {
                "n": int(len(gdf)),
                "age": safe_stats(gdf["age"]) if "age" in gdf.columns else None,
            }
    print(f"  ✓ n={len(df)}, 分组: {list(ds.get('by_group', {}).keys())}")
    stats["datasets_used"].append(ds)


# ============================================================
# ds005892 PD-NC / PD-MCI / HC
# ============================================================
print("\n[ds005892 PD-MCI vs PD-NC vs HC fMRI]")
src5892 = SRC / "ds005892" / "participants.tsv"
if src5892.exists():
    df = pd.read_csv(src5892, sep="\t")
    df.columns = [c.strip() for c in df.columns]
    ds = {
        "id": "ds005892",
        "title": "PD-MCI / PD-NC / HC Resting MRI",
        "n_total": int(len(df)),
        "use_case": "MCI 鉴别诊断 (PD-MCI 与 AD-MCI EEG/fMRI 区别) — 写进 KB 当鉴别条目",
        "by_group": {},
    }
    if "group" in df.columns:
        for grp, gdf in df.groupby("group"):
            ds["by_group"][str(grp)] = {
                "n": int(len(gdf)),
                "age": safe_stats(gdf["age"]) if "age" in gdf.columns else None,
            }
    print(f"  ✓ n={len(df)}, 分组: {list(ds.get('by_group', {}).keys())}")
    stats["datasets_used"].append(ds)


# ============================================================
# 汇总
# ============================================================
stats["summary"] = {
    "total_datasets": len(stats["datasets_used"]),
    "all_locally_available": True,
    "no_waiting": "全部基于已下载的 participants.tsv, 立即可用",
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(f"\n✓ 写入: {OUT}")
print(f"  共扩展 {len(stats['datasets_used'])} 个数据集")
print(f"  ★ 全部已下载, 不需任何申请")
