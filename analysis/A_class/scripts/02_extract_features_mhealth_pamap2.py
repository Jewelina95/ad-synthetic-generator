"""mHealth + PAMAP2 feature extraction.
mHealth: cols 14-16 wrist (right_lower_arm) acc xyz @50 Hz, col 23 label, no PPG.
        Use ECG (col 3-4) to estimate HR.
PAMAP2: col 2 = HR (bpm) @9 Hz; cols 4-6 hand acc16g @100 Hz; col 1 = activity id.

Output: features/mhealth_features.csv, features/pamap2_features.csv
"""
import os, json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks, welch

ROOT = Path("/Volumes/T7 Shield/AD/DATASETS")
OUT = Path("/Users/wenshaoyue/Desktop/research/AD generator/analysis/A_class/features")
OUT.mkdir(parents=True, exist_ok=True)

WIN_SEC = 60
STRIDE_SEC = 30


def bandpass(x, low, high, fs, order=3):
    b, a = butter(order, [low/(fs/2), high/(fs/2)], btype="band")
    return filtfilt(b, a, x)


def hr_from_ecg(ecg, fs):
    """Estimate HR/HRV from ECG by R-peak detection."""
    if len(ecg) < fs * 5:
        return np.nan, np.nan
    try:
        x = bandpass(ecg - np.mean(ecg), 5, 15, fs)
    except Exception:
        return np.nan, np.nan
    peaks, _ = find_peaks(x, distance=int(fs*60/200), height=np.std(x)*1.5)
    if len(peaks) < 4:
        return np.nan, np.nan
    ibi = np.diff(peaks) / fs * 1000
    ibi = ibi[(ibi > 300) & (ibi < 1500)]
    if len(ibi) < 3:
        return np.nan, np.nan
    return float(60000.0/np.mean(ibi)), float(np.sqrt(np.mean(np.diff(ibi)**2)))


def imu_features(acc_xyz, fs):
    if len(acc_xyz) < fs * 5:
        return [np.nan]*5
    mag = np.linalg.norm(acc_xyz, axis=1)
    jerk = np.diff(mag) * fs
    f, P = welch(mag - np.mean(mag), fs=fs, nperseg=min(len(mag), int(fs*4)))
    m = (f >= 0.5) & (f <= 3.5)
    dom = float(f[m][np.argmax(P[m])]) if m.any() else np.nan
    return [
        float(np.mean(mag)), float(np.std(mag)),
        float(np.mean(np.abs(mag - np.mean(mag)))),
        float(np.std(jerk)), dom
    ]


# ---------- mHealth ----------
def process_mhealth():
    mh_dir = ROOT / "mHealth/MHEALTHDATASET"
    files = sorted(Path(mh_dir).glob("mHealth_subject*.log"))
    fs = 50
    label_map = {1:"standing", 2:"sitting", 3:"lying", 4:"walking", 5:"stairs",
                 6:"waist_bends", 7:"arm_elev", 8:"knee_bends", 9:"cycling",
                 10:"jogging", 11:"running", 12:"jump"}
    win = int(WIN_SEC * fs)
    stride = int(STRIDE_SEC * fs)
    rows = []
    for f in files:
        sid = f.stem.replace("mHealth_subject", "S")
        df = pd.read_csv(f, sep="\t", header=None)
        # cols: 0-2 chest_acc, 3-4 ecg, 5-7 ankle_acc, 8-10 ankle_gyro, 11-13 ankle_mag,
        # 14-16 wrist_acc (right lower arm), 17-19 wrist_gyro, 20-22 wrist_mag, 23 label
        ecg = df[3].values  # ecg lead 1
        wrist_acc = df[[14, 15, 16]].values
        labels = df[23].values
        for i in range(0, len(df) - win, stride):
            seg_lab = labels[i:i+win]
            vals, counts = np.unique(seg_lab, return_counts=True)
            dom = int(vals[np.argmax(counts)])
            if dom == 0 or dom not in label_map:
                continue
            if counts[np.argmax(counts)] / len(seg_lab) < 0.8:
                continue
            hr, rmssd = hr_from_ecg(ecg[i:i+win], fs)
            imu = imu_features(wrist_acc[i:i+win], fs)
            rows.append({
                "subject": sid, "t_start": i/fs, "label": dom,
                "condition": label_map[dom],
                "mean_hr": hr, "rmssd": rmssd, "sdnn": np.nan,
                "acc_mag_mean": imu[0], "acc_mag_std": imu[1],
                "acc_mad": imu[2], "jerk_std": imu[3], "dom_freq_hz": imu[4]
            })
    df_out = pd.DataFrame(rows); df_out["dataset"] = "mHealth"
    df_out.to_csv(OUT / "mhealth_features.csv", index=False)
    print(f"mHealth: {len(df_out)} windows from {df_out.subject.nunique()} subjects")


# ---------- PAMAP2 ----------
def process_pamap2():
    pamap = ROOT / "PAMAP2/PAMAP2_Dataset/Protocol"
    files = sorted(Path(pamap).glob("subject*.dat"))
    fs_imu = 100
    fs_hr = 9
    activity_map = {
        1:"lying", 2:"sitting", 3:"standing", 4:"walking", 5:"running",
        6:"cycling", 7:"nordic_walking", 9:"watching_tv", 10:"computer",
        11:"car_driving", 12:"asc_stairs", 13:"desc_stairs", 16:"vacuum",
        17:"ironing", 18:"folding_laundry", 19:"house_cleaning",
        20:"soccer", 24:"rope_jumping"
    }
    win = int(WIN_SEC * fs_imu)
    stride = int(STRIDE_SEC * fs_imu)
    rows = []
    for f in files:
        sid = f.stem  # subject101
        # Read with NaN handling
        df = pd.read_csv(f, sep=" ", header=None, na_values=["NaN"])
        labels = df[1].values  # activity id
        hr = df[2].values  # bpm, often NaN at non-9Hz samples
        hand_acc = df[[4, 5, 6]].values  # hand acc16g
        for i in range(0, len(df) - win, stride):
            seg_lab = labels[i:i+win]
            vals, counts = np.unique(seg_lab[~np.isnan(seg_lab)], return_counts=True)
            if len(vals) == 0:
                continue
            dom = int(vals[np.argmax(counts)])
            if dom == 0 or dom not in activity_map:
                continue
            if counts[np.argmax(counts)] / np.sum(counts) < 0.8:
                continue
            seg_hr = hr[i:i+win]
            seg_hr = seg_hr[~np.isnan(seg_hr)]
            mean_hr = float(np.mean(seg_hr)) if len(seg_hr) > 0 else np.nan
            seg_acc = hand_acc[i:i+win]
            valid = ~np.isnan(seg_acc).any(axis=1)
            seg_acc = seg_acc[valid]
            imu = imu_features(seg_acc, fs_imu)
            # Crude HRV from HR series (small)
            rmssd = float(np.std(np.diff(seg_hr))) if len(seg_hr) > 2 else np.nan
            rows.append({
                "subject": sid, "t_start": i/fs_imu, "label": dom,
                "condition": activity_map[dom],
                "mean_hr": mean_hr, "rmssd": rmssd, "sdnn": np.nan,
                "acc_mag_mean": imu[0], "acc_mag_std": imu[1],
                "acc_mad": imu[2], "jerk_std": imu[3], "dom_freq_hz": imu[4]
            })
    df_out = pd.DataFrame(rows); df_out["dataset"] = "PAMAP2"
    df_out.to_csv(OUT / "pamap2_features.csv", index=False)
    print(f"PAMAP2: {len(df_out)} windows from {df_out.subject.nunique()} subjects")


if __name__ == "__main__":
    process_mhealth()
    process_pamap2()
