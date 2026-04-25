"""为网站提取 sensor 波形样本
对每个 patient 抽取 Day 0 (健康) 和 Day 25 (进展) 的 sensor 数据样本
方便网站对比展示退化效果
"""

import pandas as pd
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "data" / "synthetic"
WEB_OUT = ROOT / "docs" / "data" / "patients"

# 取每个 patient 的 walking_normal 任务在 4 个时间点
SAMPLE_DAYS = [0, 7, 14, 25]
TASK = "walking_normal"
N_POINTS_PER_DAY = 500   # 取每天前 500 行 (10 秒, 50Hz)
COLS_TO_KEEP = ["timestamp", "gsr_filtered", "hr_bpm_avg", "imu_ax_mps2", "imu_ay_mps2", "imu_az_mps2", "svm", "jerk"]

for patient_dir in sorted(SYNTHETIC.iterdir()):
    if not patient_dir.is_dir():
        continue
    pid = patient_dir.name
    if not pid.startswith("P"):
        continue

    print(f"\n=== {pid} ===")

    web_pdir = WEB_OUT / pid
    web_pdir.mkdir(exist_ok=True, parents=True)
    samples = {}

    for day in SAMPLE_DAYS:
        sensor_file = patient_dir / "sensor" / f"day{day:02d}_{TASK}.csv"
        if not sensor_file.exists():
            print(f"  ⚠ Day {day} {TASK} 不存在")
            continue

        df = pd.read_csv(sensor_file)
        # 取存在的列
        cols = [c for c in COLS_TO_KEEP if c in df.columns]
        sub = df[cols].head(N_POINTS_PER_DAY).copy()

        # 数据轻量化: float 保留 3 位 + 转 dict
        for c in sub.select_dtypes(include='float').columns:
            sub[c] = sub[c].round(3)

        records = sub.fillna("").astype(object).where(sub.notna(), None).to_dict(orient="list")

        samples[f"day_{day}"] = {
            "day": day,
            "task": TASK,
            "n_points": len(sub),
            "duration_s": len(sub) / 50,
            "data": records,
        }
        # stats
        if "hr_bpm_avg" in df.columns:
            hr = df["hr_bpm_avg"].dropna()
            hr = hr[hr > 0]
            samples[f"day_{day}"]["hr_stats"] = {
                "mean": float(hr.mean()) if len(hr) else None,
                "min": float(hr.min()) if len(hr) else None,
                "max": float(hr.max()) if len(hr) else None,
                "std": float(hr.std()) if len(hr) else None,
            }
        if "gsr_filtered" in df.columns:
            gsr = df["gsr_filtered"].dropna()
            samples[f"day_{day}"]["gsr_stats"] = {
                "mean": float(gsr.mean()) if len(gsr) else None,
                "std": float(gsr.std()) if len(gsr) else None,
            }
        if "svm" in df.columns:
            svm = df["svm"].dropna()
            samples[f"day_{day}"]["svm_stats"] = {
                "mean": float(svm.mean()) if len(svm) else None,
                "std": float(svm.std()) if len(svm) else None,
            }
        print(f"  ✓ Day {day}: {len(sub)} points, HR μ={hr.mean():.0f}, GSR μ={gsr.mean():.0f}")

    # 写出
    out_file = web_pdir / "sensor_samples.json"
    with open(out_file, "w") as f:
        json.dump(samples, f, ensure_ascii=False)
    size_kb = out_file.stat().st_size / 1024
    print(f"  ★ 写入 {out_file.name}: {size_kb:.0f} KB")

print("\n✓ 所有患者 sensor 样本提取完成")
