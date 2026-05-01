"""Extract per-window features from WESAD & PPG-DaLiA.

For each subject, slide a 60-sec window with 30-sec stride over wrist signals.
Compute per-window:
  PPG-derived: mean_HR, HRV (RMSSD), HR_range, signal quality (envelope std)
  IMU-derived: |acc|_mean, |acc|_std, jerk_std, dominant_freq (step rate), MAD
  Label: dominant condition/activity in that window

Output: features/wesad_features.csv, features/dalia_features.csv
"""
import os, pickle, json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks, welch

ROOT = Path("/Volumes/T7 Shield/AD/DATASETS")
OUT = Path("/Users/wenshaoyue/Desktop/research/AD generator/analysis/A_class/features")
OUT.mkdir(parents=True, exist_ok=True)

# Sampling rates (BVP=PPG, ACC=IMU, label)
FS_BVP = 64
FS_ACC = 32
FS_LABEL = 700  # WESAD label is at 700 Hz (chest sampling)
FS_DALIA_LABEL = 4   # DaLiA activity csv is at 4 Hz (every 0.25 s)

WIN_SEC = 60
STRIDE_SEC = 30


def bandpass(x, low, high, fs, order=3):
    b, a = butter(order, [low/(fs/2), high/(fs/2)], btype="band")
    return filtfilt(b, a, x)


def estimate_hr(bvp, fs=FS_BVP):
    """Estimate mean HR (BPM) and RMSSD (HRV) from BVP segment."""
    if len(bvp) < fs * 5:
        return np.nan, np.nan, np.nan
    try:
        x = bandpass(bvp - np.mean(bvp), 0.7, 4.0, fs)
    except Exception:
        return np.nan, np.nan, np.nan
    # Detect peaks
    min_dist = int(fs * 60 / 200)  # max 200 BPM
    peaks, _ = find_peaks(x, distance=min_dist, height=np.std(x)*0.5)
    if len(peaks) < 4:
        return np.nan, np.nan, np.nan
    ibi = np.diff(peaks) / fs * 1000  # ms
    ibi = ibi[(ibi > 300) & (ibi < 1500)]
    if len(ibi) < 3:
        return np.nan, np.nan, np.nan
    mean_hr = 60000.0 / np.mean(ibi)
    rmssd = float(np.sqrt(np.mean(np.diff(ibi)**2)))
    sdnn = float(np.std(ibi))
    return mean_hr, rmssd, sdnn


def imu_features(acc_xyz, fs=FS_ACC):
    """ACC magnitude features. acc_xyz shape (N, 3)."""
    if len(acc_xyz) < fs * 5:
        return [np.nan]*5
    mag = np.linalg.norm(acc_xyz, axis=1)
    mag_d = mag - np.mean(mag)
    jerk = np.diff(mag) * fs
    # Dominant gait freq via Welch
    if len(mag_d) > fs * 4:
        f, P = welch(mag_d, fs=fs, nperseg=min(len(mag_d), fs*4))
        # Step freq usually 0.5–3 Hz
        m = (f >= 0.5) & (f <= 3.5)
        dom_freq = float(f[m][np.argmax(P[m])]) if m.any() else np.nan
    else:
        dom_freq = np.nan
    return [
        float(np.mean(mag)),
        float(np.std(mag)),
        float(np.mean(np.abs(mag - np.mean(mag)))),  # MAD
        float(np.std(jerk)),
        dom_freq
    ]


def slide_windows(n_samples_at_fs, fs, win_sec=WIN_SEC, stride_sec=STRIDE_SEC):
    win = int(win_sec * fs)
    stride = int(stride_sec * fs)
    return [(i, i+win) for i in range(0, n_samples_at_fs - win, stride)]


def process_wesad_subject(s_dir):
    """WESAD: wrist BVP @64Hz, wrist ACC @32Hz, label @700Hz.
    Labels: 0/5/6/7 ignore; 1=baseline, 2=stress, 3=amusement, 4=meditation."""
    pkl = s_dir / f"{s_dir.name}.pkl"
    with open(pkl, "rb") as f:
        d = pickle.load(f, encoding="latin1")
    sid = s_dir.name
    bvp = np.asarray(d["signal"]["wrist"]["BVP"]).flatten()
    acc = np.asarray(d["signal"]["wrist"]["ACC"])  # (N, 3) at 32 Hz
    label = np.asarray(d["label"]).flatten()  # at 700 Hz

    rows = []
    label_map = {1: "baseline", 2: "stress", 3: "amusement", 4: "meditation"}
    # Iterate windows in BVP timeline
    win_b = int(WIN_SEC * FS_BVP)
    str_b = int(STRIDE_SEC * FS_BVP)
    for i_b in range(0, len(bvp) - win_b, str_b):
        t_start = i_b / FS_BVP
        t_end = (i_b + win_b) / FS_BVP
        seg_bvp = bvp[i_b:i_b+win_b]
        # ACC window
        i_a = int(t_start * FS_ACC); j_a = int(t_end * FS_ACC)
        seg_acc = acc[i_a:j_a]
        # Label window (mode of 700Hz labels)
        i_l = int(t_start * FS_LABEL); j_l = int(t_end * FS_LABEL)
        seg_label = label[i_l:j_l]
        # Dominant label
        vals, counts = np.unique(seg_label, return_counts=True)
        dom_label = int(vals[np.argmax(counts)])
        if dom_label not in label_map:
            continue
        # Skip windows where dominant label coverage < 80% (transition zones)
        if counts[np.argmax(counts)] / len(seg_label) < 0.8:
            continue
        hr, rmssd, sdnn = estimate_hr(seg_bvp, FS_BVP)
        imu_feats = imu_features(seg_acc, FS_ACC)
        rows.append({
            "subject": sid, "t_start": t_start, "label": dom_label,
            "condition": label_map[dom_label],
            "mean_hr": hr, "rmssd": rmssd, "sdnn": sdnn,
            "acc_mag_mean": imu_feats[0], "acc_mag_std": imu_feats[1],
            "acc_mad": imu_feats[2], "jerk_std": imu_feats[3],
            "dom_freq_hz": imu_feats[4]
        })
    return rows


def process_dalia_subject(s_dir):
    """PPG-DaLiA: wrist BVP @64Hz, wrist ACC @32Hz, activity csv @4Hz."""
    pkl = s_dir / f"{s_dir.name}.pkl"
    with open(pkl, "rb") as f:
        d = pickle.load(f, encoding="latin1")
    sid = s_dir.name
    bvp = np.asarray(d["signal"]["wrist"]["BVP"]).flatten()
    acc = np.asarray(d["signal"]["wrist"]["ACC"])
    activity = np.asarray(d.get("activity", [])).flatten() if "activity" in d else None

    activity_map = {
        0: "transient", 1: "sitting", 2: "stairs", 3: "table_soccer",
        4: "cycling", 5: "driving", 6: "lunch_break", 7: "walking", 8: "working"
    }
    rows = []
    win_b = int(WIN_SEC * FS_BVP)
    str_b = int(STRIDE_SEC * FS_BVP)
    for i_b in range(0, len(bvp) - win_b, str_b):
        t_start = i_b / FS_BVP
        t_end = (i_b + win_b) / FS_BVP
        seg_bvp = bvp[i_b:i_b+win_b]
        i_a = int(t_start * FS_ACC); j_a = int(t_end * FS_ACC)
        seg_acc = acc[i_a:j_a]
        # Dominant activity (4 Hz)
        if activity is not None and len(activity) > 0:
            i_act = int(t_start * FS_DALIA_LABEL)
            j_act = int(t_end * FS_DALIA_LABEL)
            seg_act = activity[i_act:j_act] if j_act <= len(activity) else activity[i_act:]
            if len(seg_act) == 0:
                continue
            vals, counts = np.unique(seg_act, return_counts=True)
            dom_label = int(vals[np.argmax(counts)])
            if counts[np.argmax(counts)] / len(seg_act) < 0.8:
                continue
            cond = activity_map.get(dom_label, f"act_{dom_label}")
        else:
            dom_label = -1; cond = "unknown"
        if dom_label == 0:  # skip transient
            continue
        hr, rmssd, sdnn = estimate_hr(seg_bvp, FS_BVP)
        imu_feats = imu_features(seg_acc, FS_ACC)
        rows.append({
            "subject": sid, "t_start": t_start, "label": dom_label,
            "condition": cond,
            "mean_hr": hr, "rmssd": rmssd, "sdnn": sdnn,
            "acc_mag_mean": imu_feats[0], "acc_mag_std": imu_feats[1],
            "acc_mad": imu_feats[2], "jerk_std": imu_feats[3],
            "dom_freq_hz": imu_feats[4]
        })
    return rows


def main():
    # WESAD
    wesad_dir = ROOT / "WESAD/WESAD"
    wesad_subjects = sorted([d for d in wesad_dir.iterdir() if d.is_dir() and d.name.startswith("S")])
    all_rows = []
    for s in wesad_subjects:
        print(f"WESAD {s.name} ...", flush=True)
        rows = process_wesad_subject(s)
        print(f"  -> {len(rows)} windows")
        all_rows.extend(rows)
    df_w = pd.DataFrame(all_rows)
    df_w["dataset"] = "WESAD"
    df_w.to_csv(OUT / "wesad_features.csv", index=False)
    print(f"WESAD: {len(df_w)} windows, saved.")

    # PPG-DaLiA
    dalia_dir = ROOT / "PPG-DaLiA/PPG_FieldStudy"
    dalia_subjects = sorted([d for d in dalia_dir.iterdir() if d.is_dir() and d.name.startswith("S")])
    all_rows = []
    for s in dalia_subjects:
        print(f"DaLiA {s.name} ...", flush=True)
        rows = process_dalia_subject(s)
        print(f"  -> {len(rows)} windows")
        all_rows.extend(rows)
    df_d = pd.DataFrame(all_rows)
    df_d["dataset"] = "PPG-DaLiA"
    df_d.to_csv(OUT / "dalia_features.csv", index=False)
    print(f"DaLiA: {len(df_d)} windows, saved.")


if __name__ == "__main__":
    main()
