"""Cross-dataset analysis answering the 4 research questions:
Q1. Feature: 跨数据集同活动下 HR/jerk 一致吗? → 给 generator 的 activity-HR LUT
Q2. Transformer 训练数据是否够 → 数据规模 + 同人配对统计
Q3. Claude 生成 vs 真实 → 跨模态耦合 jerk↔HR slope, 这是 B 类的 jerk-MMSE 脱钩 bug 的修复源
Q4. 评估超越 accuracy → multi-modal coupling consistency, per-subject manifold

Output:
  features/A_class_summary.json
  features/activity_hr_lut.csv  (B 类 generator 直接可用)
  features/cross_modal_coupling.json
  figures/fig1_activity_hr.png
  figures/fig2_jerk_hr_coupling.png
  figures/fig3_per_subject_manifold.png
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/wenshaoyue/Desktop/research/AD generator/analysis/A_class")
F = ROOT / "features"
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# Load
dfs = []
for name, fn in [("WESAD","wesad_features.csv"), ("PPG-DaLiA","dalia_features.csv"),
                 ("mHealth","mhealth_features.csv"), ("PAMAP2","pamap2_features.csv")]:
    df = pd.read_csv(F / fn)
    df["dataset"] = name
    dfs.append(df)
df_all = pd.concat(dfs, ignore_index=True)
df_all = df_all.dropna(subset=["mean_hr", "jerk_std"])
print(f"Loaded {len(df_all)} valid windows from {df_all.subject.nunique()} subjects.")

# ============================================================
# Q1. Activity → HR mapping (cross-dataset)
# ============================================================
# Map raw conditions to canonical buckets so we can compare across datasets
canonical_map = {
    # rest
    "baseline": "rest", "sitting": "rest", "lying": "rest", "standing": "rest",
    "watching_tv": "rest", "computer": "rest", "table_soccer": "light",
    "lunch_break": "rest", "working": "rest", "meditation": "rest",
    # light activity
    "walking": "walking", "ironing": "light", "folding_laundry": "light",
    "house_cleaning": "light", "vacuum": "light",
    "amusement": "rest",  # WESAD: video clips, low movement
    "stress": "stress",   # WESAD specific (TSST)
    "stairs": "stairs", "asc_stairs": "stairs", "desc_stairs": "stairs",
    "driving": "rest", "car_driving": "rest",
    "cycling": "moderate", "nordic_walking": "moderate",
    "running": "vigorous", "jogging": "vigorous", "rope_jumping": "vigorous",
    "soccer": "vigorous", "jump": "vigorous",
    "waist_bends": "light", "arm_elev": "light", "knee_bends": "light",
}
df_all["bucket"] = df_all["condition"].map(canonical_map).fillna("other")

# Per-bucket per-dataset HR + jerk stats
bucket_stats = (df_all
    .groupby(["dataset", "bucket"])
    .agg(n=("mean_hr","size"),
         hr_mean=("mean_hr","mean"), hr_std=("mean_hr","std"),
         jerk_mean=("jerk_std","mean"), jerk_std_=("jerk_std","std"),
         rmssd_mean=("rmssd","mean"))
    .reset_index())
bucket_stats.to_csv(F / "activity_hr_lut.csv", index=False)
print("\n=== Activity → HR cross-dataset (LUT for generator) ===")
print(bucket_stats.pivot_table(index="bucket", columns="dataset", values="hr_mean").round(1).to_string())
print("\n=== Activity → jerk_std cross-dataset ===")
print(bucket_stats.pivot_table(index="bucket", columns="dataset", values="jerk_mean").round(2).to_string())

# ============================================================
# Q3. Cross-modal coupling: jerk_std ↔ mean_hr (this fixes B-class bug)
# ============================================================
# Per-dataset per-subject Spearman correlation
coupling = []
for ds in df_all.dataset.unique():
    sub_corrs = []
    for sid, g in df_all[df_all.dataset == ds].groupby("subject"):
        if len(g) < 8:
            continue
        rho, p = stats.spearmanr(g["jerk_std"], g["mean_hr"])
        if not np.isnan(rho):
            sub_corrs.append(rho)
    pooled_rho, pooled_p = stats.spearmanr(
        df_all[df_all.dataset==ds]["jerk_std"],
        df_all[df_all.dataset==ds]["mean_hr"])
    coupling.append({
        "dataset": ds,
        "n_subjects": len(sub_corrs),
        "per_subj_rho_mean": float(np.mean(sub_corrs)),
        "per_subj_rho_std": float(np.std(sub_corrs)),
        "pooled_rho": float(pooled_rho),
        "pooled_p": float(pooled_p),
    })
coupling_df = pd.DataFrame(coupling)
print("\n=== jerk_std ↔ mean_HR coupling (B-class bug fix source) ===")
print(coupling_df.to_string(index=False))
coupling_df.to_csv(F / "jerk_hr_coupling.csv", index=False)

# ============================================================
# Pooled regression: HR = a + b * log(jerk_std + 1) (whole 4-dataset)
# This is the curve B-class generator should embed
# ============================================================
df_pooled = df_all[(df_all.jerk_std > 0) & (df_all.mean_hr > 30) & (df_all.mean_hr < 200)].copy()
df_pooled["log_jerk"] = np.log1p(df_pooled["jerk_std"])
slope, intercept, r, p, se = stats.linregress(df_pooled["log_jerk"], df_pooled["mean_hr"])
pooled_law = {
    "law": "HR_bpm = intercept + slope * log(1 + jerk_std)",
    "intercept": float(intercept),
    "slope": float(slope),
    "r": float(r),
    "p": float(p),
    "n": int(len(df_pooled))
}
print(f"\n=== Pooled cross-dataset law ===")
print(f"HR = {intercept:.2f} + {slope:.2f} * log(1 + jerk_std)   (r={r:.3f}, n={len(df_pooled)})")

# ============================================================
# Q2. Transformer training data audit
# ============================================================
training_audit = {
    "n_total_windows": int(len(df_all)),
    "n_total_subjects": int(df_all.subject.nunique()),
    "by_dataset": df_all.groupby("dataset").agg(
        windows=("subject","size"),
        subjects=("subject","nunique"),
        hours=("subject", lambda s: len(s)*30/3600)
    ).to_dict(),
    "modalities_present": {
        "PPG":  ["WESAD", "PPG-DaLiA"],
        "IMU":  ["WESAD", "PPG-DaLiA", "mHealth", "PAMAP2"],
        "ECG":  ["WESAD", "PPG-DaLiA", "mHealth"],
        "HR_direct": ["PAMAP2"],
        "EDA":  ["WESAD", "PPG-DaLiA"],
        "TEMP": ["WESAD", "PPG-DaLiA", "PAMAP2"],
    },
    "verdict": ("Total ~42 hr of paired PPG+IMU (WESAD+DaLiA, 30 subj). "
                "Sufficient for fine-tuning a pretrained time-series Transformer "
                "(Chronos/Moirai/Lag-Llama) but NOT for training one from scratch. "
                "Recommended: condition-augmented diffusion fine-tune, not raw next-token.")
}

# ============================================================
# Figures
# ============================================================
plt.style.use("default")

# Fig 1: activity bucket vs HR per dataset
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
order = ["rest", "light", "walking", "stairs", "moderate", "stress", "vigorous"]
buckets_present = [b for b in order if b in df_all.bucket.unique()]
ds_order = ["WESAD", "PPG-DaLiA", "mHealth", "PAMAP2"]
colors = ["#E63946", "#457B9D", "#2A9D8F", "#F4A261"]

for i, ds in enumerate(ds_order):
    sub = df_all[df_all.dataset == ds]
    means = [sub[sub.bucket==b]["mean_hr"].mean() for b in buckets_present]
    stds = [sub[sub.bucket==b]["mean_hr"].std() for b in buckets_present]
    x = np.arange(len(buckets_present)) + (i-1.5)*0.18
    ax[0].errorbar(x, means, yerr=stds, fmt="o", color=colors[i], label=ds, capsize=3, ms=7)
ax[0].set_xticks(np.arange(len(buckets_present)))
ax[0].set_xticklabels(buckets_present, rotation=20)
ax[0].set_ylabel("Mean HR (BPM)")
ax[0].set_title("HR by activity bucket — cross-dataset")
ax[0].legend(); ax[0].grid(alpha=0.3)

for i, ds in enumerate(ds_order):
    sub = df_all[df_all.dataset == ds]
    means = [sub[sub.bucket==b]["jerk_std"].mean() for b in buckets_present]
    stds = [sub[sub.bucket==b]["jerk_std"].std() for b in buckets_present]
    x = np.arange(len(buckets_present)) + (i-1.5)*0.18
    ax[1].errorbar(x, means, yerr=stds, fmt="s", color=colors[i], label=ds, capsize=3, ms=7)
ax[1].set_xticks(np.arange(len(buckets_present)))
ax[1].set_xticklabels(buckets_present, rotation=20)
ax[1].set_ylabel("jerk_std (m/s³)")
ax[1].set_title("Movement intensity (jerk) by activity")
ax[1].legend(); ax[1].grid(alpha=0.3)
plt.tight_layout(); plt.savefig(FIG / "fig1_activity_hr_jerk.png", dpi=140); plt.close()

# Fig 2: jerk-HR coupling (the law generator should learn)
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for i, ds in enumerate(ds_order):
    sub = df_pooled[df_pooled.dataset == ds]
    axes[0].scatter(sub["log_jerk"], sub["mean_hr"], s=8, alpha=0.3, c=colors[i], label=f"{ds} (n={len(sub)})")
xs = np.linspace(df_pooled["log_jerk"].min(), df_pooled["log_jerk"].max(), 100)
axes[0].plot(xs, intercept + slope*xs, "k-", lw=2,
             label=f"HR = {intercept:.1f} + {slope:.1f}·log(1+jerk)")
axes[0].set_xlabel("log(1 + jerk_std)")
axes[0].set_ylabel("Mean HR (BPM)")
axes[0].set_title(f"Cross-dataset jerk↔HR law  (Pearson r={r:.3f}, p<{max(p,1e-300):.0e})")
axes[0].legend(loc="upper left"); axes[0].grid(alpha=0.3)

# Fig 2b: per-dataset Spearman rho of jerk-HR
axes[1].barh(coupling_df["dataset"], coupling_df["pooled_rho"], color=colors)
for i, (rho, n) in enumerate(zip(coupling_df["pooled_rho"], coupling_df["n_subjects"])):
    axes[1].text(rho + 0.01, i, f"ρ={rho:.2f}  (n={n})", va="center", fontsize=10)
axes[1].axvline(0, color="k", lw=1)
axes[1].set_xlabel("Spearman ρ (jerk_std ↔ mean_HR)")
axes[1].set_title("Per-dataset cross-modal coupling strength")
axes[1].set_xlim(-0.1, 0.9)
axes[1].grid(alpha=0.3, axis="x")
plt.tight_layout(); plt.savefig(FIG / "fig2_jerk_hr_coupling.png", dpi=140); plt.close()

# Fig 3: per-subject 2D manifold (HR vs jerk) coloured by activity bucket
fig, axes = plt.subplots(1, 4, figsize=(20, 5), sharey=True)
bucket_palette = {"rest":"#264653", "light":"#2A9D8F", "walking":"#E9C46A",
                  "stairs":"#F4A261", "moderate":"#E76F51", "stress":"#9B5DE5",
                  "vigorous":"#E63946", "other":"#bbbbbb"}
for ax_, ds in zip(axes, ds_order):
    sub = df_all[df_all.dataset == ds]
    for b, c in bucket_palette.items():
        s = sub[sub.bucket == b]
        ax_.scatter(s["jerk_std"], s["mean_hr"], s=8, alpha=0.5, c=c, label=b)
    ax_.set_title(f"{ds}  (n={sub.subject.nunique()} subj)")
    ax_.set_xlabel("jerk_std")
    ax_.set_xscale("log")
axes[0].set_ylabel("HR (BPM)")
axes[-1].legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
plt.tight_layout(); plt.savefig(FIG / "fig3_subject_manifold.png", dpi=140); plt.close()

# ============================================================
# Save unified summary
# ============================================================
summary = {
    "n_total_windows": int(len(df_all)),
    "n_total_subjects": int(df_all.subject.nunique()),
    "training_audit": training_audit,
    "pooled_jerk_hr_law": pooled_law,
    "per_dataset_coupling": coupling,
    "activity_hr_lut": bucket_stats.to_dict(orient="records"),
}
def coerce(o):
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, (np.integer, np.int64)): return int(o)
    if isinstance(o, (np.floating, np.float64)): return float(o)
    if isinstance(o, dict): return {str(k): coerce(v) for k,v in o.items()}
    if isinstance(o, list): return [coerce(x) for x in o]
    return o
with open(F / "A_class_summary.json", "w") as fh:
    json.dump(coerce(summary), fh, indent=2, default=str)
print("\n=== Saved features/A_class_summary.json + 3 figures ===")
