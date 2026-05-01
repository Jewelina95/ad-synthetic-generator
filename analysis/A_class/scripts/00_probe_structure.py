"""Probe internal structure of A-class datasets (WESAD, PPG-DaLiA, mHealth, PAMAP2).

Output: dataset_structure.json with channels, fs, n_subjects, n_samples, labels.
"""
import os, json, pickle, glob
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path("/Volumes/T7 Shield/AD/DATASETS")
OUT = Path("/Users/wenshaoyue/Desktop/research/AD generator/analysis/A_class/features/dataset_structure.json")

result = {}

# ---------- WESAD ----------
wesad_dir = ROOT / "WESAD/WESAD"
subjects = sorted([d.name for d in wesad_dir.iterdir() if d.is_dir() and d.name.startswith("S")])
print(f"WESAD subjects: {subjects}")
S2_pkl = wesad_dir / "S2/S2.pkl"
with open(S2_pkl, "rb") as f:
    d = pickle.load(f, encoding="latin1")
wesad_struct = {
    "subjects": subjects,
    "n_subjects": len(subjects),
    "S2_keys": list(d.keys()),
    "signal_keys": list(d["signal"].keys()) if "signal" in d else None,
    "chest_channels": {k: np.asarray(v).shape for k, v in d["signal"]["chest"].items()},
    "wrist_channels": {k: np.asarray(v).shape for k, v in d["signal"]["wrist"].items()},
    "label_unique": np.unique(d["label"]).tolist(),
    "label_shape": np.asarray(d["label"]).shape,
    "subject_id": d.get("subject", "?"),
}
result["WESAD"] = wesad_struct
print("WESAD probed.")

# ---------- PPG-DaLiA ----------
dalia_dir = ROOT / "PPG-DaLiA/PPG_FieldStudy"
dalia_subjects = sorted([d.name for d in dalia_dir.iterdir() if d.is_dir() and d.name.startswith("S")])
S1_pkl = dalia_dir / "S1/S1.pkl"
with open(S1_pkl, "rb") as f:
    d = pickle.load(f, encoding="latin1")
dalia_struct = {
    "subjects": dalia_subjects,
    "n_subjects": len(dalia_subjects),
    "S1_keys": list(d.keys()),
    "signal_keys": list(d["signal"].keys()) if "signal" in d else None,
    "chest_channels": {k: np.asarray(v).shape for k, v in d["signal"]["chest"].items()},
    "wrist_channels": {k: np.asarray(v).shape for k, v in d["signal"]["wrist"].items()},
    "label_shape": np.asarray(d.get("label", [])).shape,
    "activity_unique": np.unique(d.get("activity", [])).tolist() if "activity" in d else None,
}
result["PPG-DaLiA"] = dalia_struct
print("PPG-DaLiA probed.")

# Check activity csv
act_csv = dalia_dir / "S1/S1_activity.csv"
if act_csv.exists():
    df = pd.read_csv(act_csv, sep="\t" if open(act_csv).readline().count("\t") > 0 else ",")
    dalia_struct["activity_csv_cols"] = list(df.columns)[:5] if len(df.columns) > 0 else []
    dalia_struct["activity_csv_head"] = df.head(3).to_dict() if len(df) > 0 else None

# ---------- mHealth ----------
mhealth_dir = ROOT / "mHealth/MHEALTHDATASET"
mh_files = sorted(glob.glob(str(mhealth_dir / "mHealth_subject*.log")))
sample = pd.read_csv(mh_files[0], sep="\t", header=None, nrows=10)
all_lengths = []
for f in mh_files[:3]:
    with open(f) as fh:
        all_lengths.append(sum(1 for _ in fh))
mhealth_struct = {
    "n_subjects": len(mh_files),
    "n_columns": sample.shape[1],
    "fs_hz": 50,
    "sample_lens_first3": all_lengths,
    "duration_sec_first3": [n/50 for n in all_lengths],
    "label_col": 23,
    "label_unique_S1": pd.read_csv(mh_files[0], sep="\t", header=None, usecols=[23])[23].unique().tolist(),
    "channel_layout": [
        "0-2:chest_acc_xyz", "3-4:ecg_l1_l2",
        "5-7:ankle_acc_xyz", "8-10:ankle_gyro_xyz", "11-13:ankle_mag_xyz",
        "14-16:wrist_acc_xyz", "17-19:wrist_gyro_xyz", "20-22:wrist_mag_xyz",
        "23:label"
    ],
    "activities": ["L1:standing", "L2:sitting", "L3:lying", "L4:walking", "L5:stairs",
                   "L6:waist_bends", "L7:arm_elev", "L8:knee_bends", "L9:cycling",
                   "L10:jogging", "L11:running", "L12:jump"]
}
result["mHealth"] = mhealth_struct
print("mHealth probed.")

# ---------- PAMAP2 ----------
pamap_dir = ROOT / "PAMAP2/PAMAP2_Dataset"
proto_files = sorted(glob.glob(str(pamap_dir / "Protocol/subject*.dat")))
sample = pd.read_csv(proto_files[0], sep=" ", header=None, nrows=100)
total_lines = sum(1 for _ in open(proto_files[0]))
pamap_struct = {
    "n_subjects_protocol": len(proto_files),
    "n_subjects_optional": len(glob.glob(str(pamap_dir / "Optional/subject*.dat"))),
    "n_columns": sample.shape[1],
    "fs_imu_hz": 100,
    "fs_hr_hz": 9,
    "duration_sec_S1_protocol": total_lines/100,
    "duration_min_S1_protocol": total_lines/100/60,
    "channel_layout": [
        "0:timestamp_sec", "1:activity_id", "2:HR_bpm",
        "3:hand_temp", "4-6:hand_acc16g_xyz", "7-9:hand_acc6g_xyz",
        "10-12:hand_gyro_xyz", "13-15:hand_mag_xyz", "16-19:hand_orientation",
        "20:chest_temp", "21-23:chest_acc16g", "24-26:chest_acc6g",
        "27-29:chest_gyro", "30-32:chest_mag", "33-36:chest_orientation",
        "37:ankle_temp", "38-40:ankle_acc16g", "41-43:ankle_acc6g",
        "44-46:ankle_gyro", "47-49:ankle_mag", "50-53:ankle_orientation"
    ],
    "label_col": 1,
    "label_unique_S1": sorted(pd.read_csv(proto_files[0], sep=" ", header=None,
                                          usecols=[1])[1].unique().tolist()),
    "activities_lookup": {
        "1": "lying", "2": "sitting", "3": "standing", "4": "walking",
        "5": "running", "6": "cycling", "7": "Nordic walking", "9": "TV",
        "10": "computer", "11": "car", "12": "ascending stairs",
        "13": "descending stairs", "16": "vacuum", "17": "ironing",
        "18": "folding laundry", "19": "house cleaning", "20": "soccer",
        "24": "rope jumping", "0": "transient/no activity"
    }
}
result["PAMAP2"] = pamap_struct
print("PAMAP2 probed.")

# Save
OUT.parent.mkdir(parents=True, exist_ok=True)
def coerce(o):
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, (np.integer, np.int64)): return int(o)
    if isinstance(o, (np.floating, np.float64)): return float(o)
    if isinstance(o, tuple): return list(o)
    if isinstance(o, dict): return {k: coerce(v) for k, v in o.items()}
    if isinstance(o, list): return [coerce(x) for x in o]
    return o

with open(OUT, "w") as f:
    json.dump(coerce(result), f, indent=2, default=str)
print(f"\nWrote {OUT}")

# Summary print
for ds, s in result.items():
    print(f"\n=== {ds} ===")
    n = s.get("n_subjects") or s.get("n_subjects_protocol")
    print(f"  n_subjects: {n}")
    if ds == "WESAD":
        print(f"  chest @700Hz: {list(s['chest_channels'].keys())}")
        print(f"  wrist Empatica E4: {list(s['wrist_channels'].keys())}")
        print(f"  labels: {s['label_unique']}")
    elif ds == "PPG-DaLiA":
        print(f"  chest @700Hz: {list(s['chest_channels'].keys())}")
        print(f"  wrist Empatica E4: {list(s['wrist_channels'].keys())}")
    elif ds == "mHealth":
        print(f"  cols: {s['n_columns']} @ {s['fs_hz']}Hz, dur≈{s['duration_sec_first3'][0]:.0f}s")
        print(f"  labels: {sorted(s['label_unique_S1'])}")
    elif ds == "PAMAP2":
        print(f"  cols: {s['n_columns']} @ IMU {s['fs_imu_hz']}Hz, HR {s['fs_hr_hz']}Hz")
        print(f"  duration: {s['duration_min_S1_protocol']:.1f} min S1")
        print(f"  labels: {s['label_unique_S1']}")
