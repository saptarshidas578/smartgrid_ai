# Raw Datasets Documentation

This directory contains the experimental and operational datasets collected from the cyber-physical smart grid testbed:

## Datasets Overview

| File | Rows / Samples | Sampling Rate | Description |
| :--- | :--- | :--- | :--- |
| `master_grid_dataset.csv` | 5,200 | 2.0 s (0.5 Hz) | Master training dataset with nominal current draws, source transitions, and sequential load states across all 5 sectors. |
| `fault_grid_dataset_labeled.csv` | 3,120 | 2.0 s (0.5 Hz) | Multi-class labeled fault dataset covering overcurrent, undercurrent, open circuits, and welded contactors (`RELAY_OFF_CURRENT_DRAWN`). |
| `fault_grid_dataset.csv` | 2,400 | 2.0 s (0.5 Hz) | Raw unregularized fault injection logs from early hardware bench testing. |
| `uniform_grid_dataset.csv` | 1,850 | 2.0 s (0.5 Hz) | Regularized steady-state baseline telemetry with uniform timestamp steps. |
| `esp_grid_telemetry.xlsx` | 3,495 | 2.0 s (0.5 Hz) | Physical hardware telemetry logs captured directly over MQTT from the ESP32 microcontroller in the laboratory. |

## Feature Schema

Each tabular dataset records the following electrical and topological columns:
- `timestamp`: UTC/IST formatted sample timestamp (`YYYY-MM-DD HH:MM:SS`)
- `mode`: Operating generation mode (`DUAL SMPS`, `SINGLE SMPS`, `BATTERY`)
- `current_limit`: Dynamic maximum available current capacity in mA (5000 mA, 1000 mA, 800 mA)
- `critical_voltage`, `critical_current`, `critical_power`: Non-sheddable protected sector readings (12V nominal, ~300 mA)
- `<load>_voltage`, `<load>_current`, `<load>_power`: Sector electrical measurements where `<load>` is `hospital`, `street`, `house`, `industry`
- `<load>_relay`: Contactor state (`1` = CLOSED / ON, `0` = OPEN / OFF)
- `total_current`, `total_power`: Total busbar demand
- `fault_detected`, `fault_load`, `fault_type`, `severity`: Diagnostic labels applied during fault injection testing.
