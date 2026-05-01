"""Evaluate B-class synthetic data against A-class real coupling laws.

For each synthetic CSV (walking_normal task), compute the same window features:
mean_HR, jerk_std. Then compare:
1. jerk_std ↔ HR coupling (generator should be ρ≈0.5+ per A-class real, current is ρ=0.08)
2. Distribution overlap with A-class real walking windows
3. Activity-bucket HR fall in expected range?

Output: features/eval_generator_vs_real.json + figures/fig4_gen_vs_real.png
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from scipy.signal import welch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import glob

ROOT = Path("/Users/wenshaoyue/Desktop/research/AD generator")
F = ROOT / "analysis/A_class/features"
FIG = ROOT / "analysis/A_class/figures"
SYN = ROOT / "data/synthetic/by_task/walking_normal"

WIN_SEC = 60
STRIDE_SEC = 30
FS = 50  # B-class generator sampling rate

def imu_jerk(acc_xyz, fs):
    if len(acc_xyz) < fs * 5:
        return np.nan
    mag = np.linalg.norm(acc_xyz, axis=1)
    jerk = np.diff(mag) * fs
    return float(np.std(jerk))

# ---- Sample B-class synthetic walking_normal across patients/days ----
syn_files = sorted(glob.glob(str(SYN / "P*_day*.csv")))[:80]  # first 80 files
print(f"Found {len(syn_files)} synthetic walking_normal files")
syn_rows = []
for fp in syn_files:
    try:
        df = pd.read_csv(fp)
    except Exception:
        continue
    if len(df) < WIN_SEC * FS:
        continue
    win = WIN_SEC * FS
    stride = STRIDE_SEC * FS
    pid = df["patient_id"].iloc[0]
    day = df["day"].iloc[0]
    progression = df["progression"].iloc[0]
    for i in range(0, len(df) - win, stride):
        seg = df.iloc[i:i+win]
        acc = seg[["imu_ax_mps2","imu_ay_mps2","imu_az_mps2"]].values
        hr = seg["hr_bpm_avg"].dropna().values
        if len(hr) == 0:
            continue
        syn_rows.append({
            "patient": pid, "day": int(day), "progression": float(progression),
            "mean_hr": float(np.nanmean(hr)),
            "jerk_std": imu_jerk(acc, FS)
        })
df_syn = pd.DataFrame(syn_rows).dropna()
print(f"Synthetic: {len(df_syn)} windows, {df_syn.patient.nunique()} patients")

# ---- Real walking from A class ----
df_real = pd.concat([pd.read_csv(F / f) for f in
                     ["wesad_features.csv","dalia_features.csv",
                      "mhealth_features.csv","pamap2_features.csv"]], ignore_index=True)
df_real = df_real[df_real["condition"].isin(["walking", "asc_stairs", "desc_stairs", "stairs",
                                              "nordic_walking"])].dropna(subset=["mean_hr","jerk_std"])
print(f"Real walking: {len(df_real)} windows from {df_real.subject.nunique()} subjects")

# ---- Eval ----
rho_syn, p_syn = stats.spearmanr(df_syn["jerk_std"], df_syn["mean_hr"])
rho_real, p_real = stats.spearmanr(df_real["jerk_std"], df_real["mean_hr"])

# KS on HR / jerk distributions
ks_hr = stats.ks_2samp(df_syn["mean_hr"], df_real["mean_hr"])
ks_jerk = stats.ks_2samp(df_syn["jerk_std"], df_real["jerk_std"])

eval_report = {
    "n_windows_synthetic": int(len(df_syn)),
    "n_windows_real_walking": int(len(df_real)),
    "n_subjects_real": int(df_real.subject.nunique()),
    "synthetic_jerk_hr_rho": float(rho_syn),
    "synthetic_jerk_hr_p": float(p_syn),
    "real_jerk_hr_rho": float(rho_real),
    "real_jerk_hr_p": float(p_real),
    "rho_gap": float(rho_real - rho_syn),
    "verdict_coupling": ("BUG CONFIRMED" if abs(rho_syn) < 0.2 and rho_real > 0.4
                         else "OK" if abs(rho_syn-rho_real) < 0.15 else "WEAK"),
    "ks_hr_statistic": float(ks_hr.statistic),
    "ks_hr_p": float(ks_hr.pvalue),
    "ks_jerk_statistic": float(ks_jerk.statistic),
    "ks_jerk_p": float(ks_jerk.pvalue),
    "synthetic_hr_mean": float(df_syn.mean_hr.mean()),
    "synthetic_hr_std": float(df_syn.mean_hr.std()),
    "real_walking_hr_mean": float(df_real.mean_hr.mean()),
    "real_walking_hr_std": float(df_real.mean_hr.std()),
    "synthetic_jerk_mean": float(df_syn.jerk_std.mean()),
    "real_jerk_mean": float(df_real.jerk_std.mean()),
}
print("\n=== Generator vs Real Eval ===")
for k, v in eval_report.items():
    print(f"  {k}: {v}")

# ---- Figure ----
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
# 1. jerk vs HR scatter overlay
ax[0].scatter(df_real["jerk_std"], df_real["mean_hr"], s=10, alpha=0.4,
              c="#2A9D8F", label=f"Real walking n={len(df_real)}")
ax[0].scatter(df_syn["jerk_std"], df_syn["mean_hr"], s=12, alpha=0.5,
              c="#E63946", label=f"B-class synthetic n={len(df_syn)}")
ax[0].set_xscale("log"); ax[0].set_xlabel("jerk_std")
ax[0].set_ylabel("Mean HR (BPM)")
ax[0].set_title(f"Coupling: real ρ={rho_real:.2f}  vs  syn ρ={rho_syn:.2f}")
ax[0].legend(); ax[0].grid(alpha=0.3)

# 2. HR distribution
ax[1].hist(df_real["mean_hr"], bins=30, alpha=0.6, color="#2A9D8F", density=True,
           label=f"Real μ={df_real.mean_hr.mean():.1f}")
ax[1].hist(df_syn["mean_hr"], bins=30, alpha=0.6, color="#E63946", density=True,
           label=f"Synthetic μ={df_syn.mean_hr.mean():.1f}")
ax[1].set_xlabel("HR (BPM)")
ax[1].set_title(f"HR distribution  KS={ks_hr.statistic:.2f} p={ks_hr.pvalue:.0e}")
ax[1].legend(); ax[1].grid(alpha=0.3)

# 3. jerk distribution
ax[2].hist(np.log1p(df_real["jerk_std"]), bins=30, alpha=0.6, color="#2A9D8F", density=True,
           label="Real")
ax[2].hist(np.log1p(df_syn["jerk_std"]), bins=30, alpha=0.6, color="#E63946", density=True,
           label="Synthetic")
ax[2].set_xlabel("log(1+jerk_std)")
ax[2].set_title(f"Jerk distribution  KS={ks_jerk.statistic:.2f} p={ks_jerk.pvalue:.0e}")
ax[2].legend(); ax[2].grid(alpha=0.3)
plt.tight_layout()
plt.savefig(FIG / "fig4_gen_vs_real.png", dpi=140)
plt.close()

with open(F / "eval_generator_vs_real.json", "w") as fh:
    json.dump(eval_report, fh, indent=2, default=str)
print(f"\nSaved {F}/eval_generator_vs_real.json + fig4_gen_vs_real.png")
