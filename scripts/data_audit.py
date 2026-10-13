import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "live_smartgrid.db")

def run_data_audit():
    print("=" * 70)
    print("  [AUDIT] SMART GRID TELEMETRY & DATASET AUDIT (PHASE 2)")
    print("=" * 70)

    audit_results = {}

    # 1. Inspect SQLite Database
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    df_tel = pd.read_sql_query("SELECT * FROM telemetry_logs ORDER BY id ASC", conn)
    df_act = pd.read_sql_query("SELECT * FROM grid_actuation_events ORDER BY id ASC", conn)
    conn.close()

    print(f"\n[1] SQLite Database: {os.path.basename(DB_PATH)} ({os.path.getsize(DB_PATH)/1024:.1f} KB)")
    print(f"  - Total Telemetry Rows : {len(df_tel)}")
    print(f"  - Total Actuation Rows : {len(df_act)}")

    # Timestamp Analysis
    df_tel["dt"] = pd.to_datetime(df_tel["timestamp"], errors="coerce")
    null_ts = df_tel["dt"].isna().sum()
    print(f"  - Invalid/Null Timestamps: {null_ts}")

    earliest = df_tel["dt"].min()
    latest = df_tel["dt"].max()
    print(f"  - Time Range: {earliest} to {latest}")

    # Duplicates Analysis
    total_rows = len(df_tel)
    unique_ts = df_tel["timestamp"].nunique()
    dup_ts_count = total_rows - unique_ts
    print(f"  - Distinct Timestamps : {unique_ts}")
    print(f"  - Duplicate Timestamps: {dup_ts_count} ({dup_ts_count/total_rows*100:.2f}%)")

    # Deep dive into duplicates
    dup_counts = df_tel.groupby("timestamp").size()
    multi_records = dup_counts[dup_counts > 1]
    print(f"  - Timestamps with >1 record: {len(multi_records)}")
    print(f"  - Max occurrences for a single timestamp: {multi_records.max() if not multi_records.empty else 0}")

    # Inspect a few duplicate groups to determine if they are identical or varying sensor readings
    sample_dups = multi_records.index[:3]
    print("\n  - Sample Duplicate Groups Inspection:")
    for s_ts in sample_dups:
        sub = df_tel[df_tel["timestamp"] == s_ts][["id", "timestamp", "mode", "current_limit", "total_current", "hospital_current", "industry_current"]]
        print(f"    Timestamp: {s_ts}")
        for _, row in sub.iterrows():
            print(f"      ID {row['id']}: Mode={row['mode']} Limit={row['current_limit']}mA Tot={row['total_current']}mA Hosp={row['hospital_current']}mA Ind={row['industry_current']}mA")

    # Time delta analysis
    df_unique = df_tel.drop_duplicates(subset=["timestamp"]).sort_values("dt").reset_index(drop=True)
    deltas = df_unique["dt"].diff().dt.total_seconds().dropna()
    print(f"\n  - Delta Distribution between Successive Unique Timestamps:")
    print(f"    * Median delta : {deltas.median():.1f} s")
    print(f"    * Mean delta   : {deltas.mean():.1f} s")
    print(f"    * Min delta    : {deltas.min():.1f} s")
    print(f"    * Max delta    : {deltas.max():.1f} s")
    print(f"    * Exactly 1-2s : {(deltas <= 2.5).sum()} ({(deltas <= 2.5).sum()/len(deltas)*100:.1f}%)")
    print(f"    * 2s to 5s     : {((deltas > 2.5) & (deltas <= 5.5)).sum()} ({((deltas > 2.5) & (deltas <= 5.5)).sum()/len(deltas)*100:.1f}%)")
    print(f"    * Gaps > 10s   : {(deltas > 10.0).sum()} (session boundaries / downtime)")

    # Data Quality & Outlier Check
    numeric_cols = [
        "hospital_current", "street_current", "house_current", "industry_current",
        "critical_current", "total_current", "total_power"
    ]
    print("\n  - Telemetry Value Quality & Health:")
    col_stats = {}
    for col in numeric_cols:
        c_min = df_tel[col].min()
        c_max = df_tel[col].max()
        c_mean = df_tel[col].mean()
        c_neg = (df_tel[col] < 0).sum()
        c_nan = df_tel[col].isna().sum()
        col_stats[col] = {"min": c_min, "max": c_max, "mean": c_mean, "negatives": int(c_neg), "nans": int(c_nan)}
        print(f"    * {col:<18}: Min={c_min:6.1f} | Max={c_max:6.1f} | Mean={c_mean:6.1f} | Negatives={c_neg} | NaNs={c_nan}")

    # Check Modes
    print("\n  - Operating Mode Distribution:")
    mode_counts = df_tel["mode"].value_counts()
    for mode_name, cnt in mode_counts.items():
        print(f"    * {mode_name:<16}: {cnt:4d} records ({cnt/len(df_tel)*100:.1f}%)")

    # 2. Inspect CSV Datasets
    csv_files = [
        "fault_grid_dataset.csv",
        "fault_grid_dataset_labeled.csv",
        "master_grid_dataset.csv",
        "uniform_grid_dataset.csv"
    ]
    print("\n[2] CSV Datasets Audit:")
    for f in csv_files:
        f_path = os.path.join(SCRIPT_DIR, f)
        if os.path.exists(f_path):
            df_csv = pd.read_csv(f_path)
            print(f"  - {f:<30}: {len(df_csv):6d} rows, {len(df_csv.columns):2d} cols ({os.path.getsize(f_path)/1024:.1f} KB)")
            # Check fault labels if present
            for lbl_col in ["fault", "fault_detected", "anomaly", "label", "fault_type"]:
                if lbl_col in df_csv.columns:
                    val_c = df_csv[lbl_col].value_counts().to_dict()
                    print(f"    Target '{lbl_col}': {val_c}")
        else:
            print(f"  - {f:<30}: NOT FOUND")

    # Regularization & De-duplication Strategy Design
    # Strategy: Group by timestamp, average currents/powers, and take max of relays and faults.
    print("\n[3] Testing Non-Destructive Regularization & Aggregation Strategy:")
    agg_rules = {
        "mode": "first",
        "current_limit": "first",
        "hospital_relay": "max",
        "hospital_current": "mean",
        "street_relay": "max",
        "street_current": "mean",
        "house_relay": "max",
        "house_current": "mean",
        "industry_relay": "max",
        "industry_current": "mean",
        "critical_current": "mean",
        "total_current": "mean",
        "total_power": "mean",
        "predicted_current": "mean",
        "predicted_power": "mean",
        "fault_detected": "max",
        "fault_load": "first",
        "fault_type": "first",
        "severity": "first",
        "warning_level": "max",
        "warning_message": "first"
    }
    # Keep only columns that exist
    valid_agg = {k: v for k, v in agg_rules.items() if k in df_tel.columns}
    df_cleaned = df_tel.groupby("timestamp", as_index=False).agg(valid_agg)
    print(f"  - Original rows : {len(df_tel)}")
    print(f"  - Regularized rows: {len(df_cleaned)}")
    print(f"  - Duplicate timestamps completely resolved: {df_cleaned['timestamp'].nunique() == len(df_cleaned)}")

    # Save summary report
    report_file = os.path.join(PROJECT_ROOT, "docs", "DATA_AUDIT_REPORT.json")
    with open(report_file, "w") as f:
        json.dump({
            "total_rows": total_rows,
            "unique_timestamps": unique_ts,
            "duplicate_timestamps": dup_ts_count,
            "time_range": [str(earliest), str(latest)],
            "numeric_stats": col_stats,
            "mode_distribution": mode_counts.to_dict(),
            "regularized_row_count": len(df_cleaned)
        }, f, indent=4)
    print(f"\nAudit summary written to: {report_file}")
    print("=" * 70)

if __name__ == "__main__":
    run_data_audit()
