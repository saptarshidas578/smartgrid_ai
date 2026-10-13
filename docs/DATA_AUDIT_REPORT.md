# Smart Grid Telemetry Data Audit & Regularization Report

**Phase**: Phase 2 — Data Audit, Timestamp Regularization & Cleaning Strategy  
**Workspace**: `DEVELOPMENT/experiment_001_baseline_verification/`  
**Analyzed Sources**: `live_smartgrid.db` (3,495 telemetry rows, 276 actuation rows) & 4 CSV datasets  
**Date**: September 16, 2026

---

## 1. Executive Summary

A comprehensive data audit was conducted on the production SQLite database (`live_smartgrid.db`) and historical training datasets. The telemetry log exhibits high integrity with **zero null or malformed timestamps**, but displays timestamp jitter and whole-second rounding collisions resulting from sub-second sampling and network latency.

| Metric | Measured Value | Operational Implication |
| :--- | :--- | :--- |
| **Total Telemetry Rows** | 3,495 rows | Sufficient volume for validation |
| **Total Actuation Events** | 276 events | Comprehensive record of trips, sheds, and restores |
| **Temporal Span** | 2026-08-27 00:00:19 to 2026-09-16 08:08:01 | Captures multi-week deployment cycles |
| **Distinct Timestamps** | 3,003 | 492 duplicate timestamp rows (14.08%) |
| **Timestamps with Duplicates** | 403 instances | Sub-second burst or dual-delivery |
| **Median Sampling Interval** | 5.0 s (historical) $\to$ 2.0 s (new mode) | 642 rows (21.4%) recorded at $\le 2.0\,\text{s}$ |
| **Sensor Zero-Offset Noise** | 24 hospital, 8 street, 1 house negative readings | Minor INA219 shunt drift ($-0.6\,\text{mA}$ to $-0.5\,\text{mA}$) |

---

## 2. Root-Cause Analysis of Duplicate Timestamps

Inspection of duplicate groups reveals that records sharing the same timestamp string are **not identical redundant writes**, but rather consecutive sensor acquisitions arriving within the same second:

```
Timestamp: 2026-09-12 19:47:49
  ID 136: Mode=DUAL SMPS | Limit=0.0mA | Total=287.9mA | Hospital=0.0mA | Industry=0.0mA
  ID 137: Mode=DUAL SMPS | Limit=0.0mA | Total=290.0mA | Hospital=0.0mA | Industry=0.0mA

Timestamp: 2026-09-12 19:49:22
  ID 229: Mode=DUAL SMPS | Limit=0.0mA | Total=773.9mA | Hospital=260.0mA | Industry=0.0mA
  ID 230: Mode=DUAL SMPS | Limit=0.0mA | Total=560.3mA | Hospital=259.8mA | Industry=0.0mA
```

**Root Cause**: The firmware NTP formatter `strftime("%Y-%m-%d %H:%M:%S")` truncates millisecond fractions. When sampling at 1–2 Hz or during network buffer flushing, multiple telemetry packets share the same integer second.

### Regularization Strategy
1. **In-Memory Telemetry Pipeline**: For live ML rolling windows, use incoming packet sequence ordering (`id` monotonic order) rather than grouping.
2. **Offline ML Training & Analytics**: Apply non-destructive temporal aggregation:
   - Continuous measurements (`current`, `power`): arithmetic `mean()` across duplicate seconds.
   - Discrete status flags (`relay`, `fault_detected`, `warning_level`): `max()` to preserve safety trip indicators.
   - Discrete labels (`mode`, `fault_type`, `severity`): `first()` or dominant state.
   - Result: Exactly 3,003 uniform records, 0% duplicates, preserving signal fidelity.
3. **Sensor Drift Clamping**: Negative currents between $-1.0\,\text{mA}$ and $0.0\,\text{mA}$ are clamped to $0.0\,\text{mA}$.

---

## 3. Training vs. Live Hardware Dataset Separation

| Dataset Filename | Rows | Columns | Characterization | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `live_smartgrid.db` | 3,495 | 22 | **100% Real Physical Hardware** | Ground-truth physical operation, bench validation |
| `master_grid_dataset.csv` | 6,309 | 33 | **Hybrid Balanced Dataset** | 3,080 Normal physical rows + 3,229 Fault Injection scenarios |
| `fault_grid_dataset_labeled.csv`| 3,200 | 31 | **Synthetic Fault Injections** | Specific failure mode benchmarking (welded relay, brownouts) |
| `uniform_grid_dataset.csv` | 3,109 | 27 | **Regularized Time Series** | Temporal sequence modeling and ARIMA/RF forecasting |
