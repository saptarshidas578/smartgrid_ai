import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", message=r".*sklearn\.utils\.parallel.*")
import joblib
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
try:
    from core.config import config
except ImportError:
    from src.core.config import config

class MLEngine:
    def __init__(self, models_dir: str = config.models_dir):
        self.models_dir = models_dir
        self.models = {}
        self.feature_headers = {}
        self.history_buffer: List[Dict[str, Any]] = []
        self.max_history_len = 35

        self.load_models()

    def load_models(self):
        required_files = {
            "forecaster_current": "load_forecasting_current_model.pkl",
            "forecaster_power": "load_forecasting_power_model.pkl",
            "forecasting_features": "forecasting_features.pkl",
            "clf_presence": "fault_detection_model.pkl",
            "clf_load": "fault_load_model.pkl",
            "clf_type": "fault_type_model.pkl",
            "clf_severity": "fault_severity_model.pkl",
            "fault_features": "fault_features.pkl",
            "model_hospital": "model_hospital.pkl",
            "model_street": "model_street.pkl",
            "model_house": "model_house.pkl",
            "model_industry": "model_industry.pkl"
        }

        print("[ML Engine] Initializing models from:", self.models_dir)
        for key, filename in required_files.items():
            path = os.path.join(self.models_dir, filename)
            if os.path.exists(path):
                try:
                    if "features" in key:
                        self.feature_headers[key] = joblib.load(path)
                    else:
                        m = joblib.load(path)
                        if hasattr(m, "n_jobs"):
                            m.n_jobs = 1
                        self.models[key] = m
                except Exception as e:
                    print(f"[ML Engine] Warning loading {filename}: {e}")
            else:
                print(f"[ML Engine] Missing file: {filename}")

    def flatten_raw_telemetry(self, data: dict) -> dict:
        raw_ts = str(data.get("timestamp", ""))
        now_dt = datetime.datetime.now()
        try:
            parsed_dt = pd.to_datetime(raw_ts)
            if parsed_dt.year >= 2020:
                clean_ts = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                clean_ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            clean_ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Clamp sensor negative readings (INA219 zero-drift)
        def clean_val(val: float) -> float:
            v = float(val or 0.0)
            return max(0.0, v)

        crit = data.get("critical", {})
        row = {
            "timestamp": clean_ts,
            "device_id": data.get("device_id", "ESP32_SMARTGRID"),
            "mode": data.get("mode", "DUAL SMPS"),
            "current_limit": float(data.get("current_limit", 5000.0)),
            "smps1": int(data.get("sources", {}).get("smps1", False)),
            "smps2": int(data.get("sources", {}).get("smps2", False)),
            "battery": int(data.get("sources", {}).get("battery", False)),
            
            "critical_voltage": clean_val(crit.get("voltage", 12.0)),
            "critical_current": clean_val(crit.get("current", 300.0)),
            "critical_power": clean_val(crit.get("power", 3600.0)),
        }

        # Loads
        load_map = {l["name"].lower(): l for l in data.get("loads", []) if isinstance(l, dict)}
        for name in ["hospital", "street", "house", "industry"]:
            load_data = load_map.get(name, {})
            row[f"{name}_voltage"] = clean_val(load_data.get("voltage", 12.0))
            row[f"{name}_current"] = clean_val(load_data.get("current", 0.0))
            row[f"{name}_power"] = clean_val(load_data.get("power", 0.0))
            relay_val = load_data.get("relay", True)
            row[f"{name}_relay"] = 1 if (relay_val is True or relay_val == 1 or relay_val == "1") else 0
            row[f"{name}_priority"] = int(load_data.get("priority", config.load_priorities.get(name, 1)))
            row[f"{name}_nominal_current"] = float(load_data.get("nominal_current", config.nominal_draws.get(name, 250.0)))

        totals = data.get("totals", {})
        calc_tot_i = row["critical_current"] + sum(row[f"{n}_current"] for n in ["hospital", "street", "house", "industry"])
        row["total_current"] = clean_val(totals.get("current", calc_tot_i))
        calc_tot_p = row["critical_power"] + sum(row[f"{n}_power"] for n in ["hospital", "street", "house", "industry"])
        row["total_power"] = clean_val(totals.get("power", calc_tot_p))

        return row

    def ensure_flat_row(self, row: dict) -> dict:
        """
        Normalizes any telemetry representation (flat DB row, raw ESP32 dict,
        or dashboard state dict) into a standard flat dictionary with all required keys.
        """
        if not isinstance(row, dict):
            row = {}

        # If it has raw nested loads list (ESP32 raw packet), use flatten_raw_telemetry
        if "loads" in row and isinstance(row["loads"], list):
            return self.flatten_raw_telemetry(row)

        sources = row.get("sources", {})
        if not isinstance(sources, dict):
            sources = {}

        crit = row.get("critical", {})
        if not isinstance(crit, dict):
            crit = {}

        mode = str(row.get("mode", "DUAL SMPS"))
        clean_row = {
            "timestamp": str(row.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            "device_id": str(row.get("device_id", "ESP32_SMARTGRID")),
            "mode": mode,
            "current_limit": float(row.get("current_limit", 5000.0)),
            "smps1": int(row.get("smps1", sources.get("smps1", 1 if ("DUAL" in mode or "SMPS 1" in mode or mode == "NORMAL") else 0))),
            "smps2": int(row.get("smps2", sources.get("smps2", 1 if ("DUAL" in mode or "SMPS 2" in mode) else 0))),
            "battery": int(row.get("battery", sources.get("battery", 1 if "BATTERY" in mode.upper() else 0))),

            "critical_voltage": float(row.get("critical_voltage", crit.get("voltage", 12.0))),
            "critical_current": float(row.get("critical_current", crit.get("current", 300.0))),
            "critical_power": float(row.get("critical_power", crit.get("power", 3600.0))),
            "critical_relay": 1
        }

        calc_tot_i = clean_row["critical_current"]
        calc_tot_p = clean_row["critical_power"]

        for load in ["hospital", "street", "house", "industry"]:
            sub = row.get(load, {})
            if not isinstance(sub, dict):
                sub = {}

            curr = float(row.get(f"{load}_current", sub.get("current", 0.0)))
            volt = float(row.get(f"{load}_voltage", sub.get("voltage", 12.0)))
            pwr = float(row.get(f"{load}_power", sub.get("power", curr * volt / 1000.0)))
            r_raw = row.get(f"{load}_relay", sub.get("relay", 1))
            relay = 1 if (r_raw is True or r_raw == 1 or r_raw == "1") else 0

            clean_row[f"{load}_current"] = max(0.0, curr)
            clean_row[f"{load}_voltage"] = max(0.0, volt)
            clean_row[f"{load}_power"] = max(0.0, pwr)
            clean_row[f"{load}_relay"] = relay
            clean_row[f"{load}_priority"] = int(row.get(f"{load}_priority", config.load_priorities.get(load, 1)))
            clean_row[f"{load}_nominal_current"] = float(row.get(f"{load}_nominal_current", config.nominal_draws.get(load, 250.0)))

            calc_tot_i += clean_row[f"{load}_current"]
            calc_tot_p += clean_row[f"{load}_power"]

        clean_row["total_current"] = float(row.get("total_current", calc_tot_i))
        clean_row["total_power"] = float(row.get("total_power", calc_tot_p))

        return clean_row

    def compute_features(self, current_row: dict) -> dict:
        flat_row = self.ensure_flat_row(current_row)
        self.history_buffer.append(flat_row)
        if len(self.history_buffer) > self.max_history_len:
            self.history_buffer.pop(0)

        df_hist = pd.DataFrame(self.history_buffer)

        try:
            dt = pd.to_datetime(flat_row["timestamp"])
            if dt.year < 2020:
                dt = datetime.datetime.now()
        except Exception:
            dt = datetime.datetime.now()

        features = {
            "hour": dt.hour,
            "minute": dt.minute,
            "day_of_week": dt.dayofweek,
            "is_weekend": 1 if dt.dayofweek >= 5 else 0,
            "mode": flat_row["mode"],
            "smps1": flat_row["smps1"],
            "smps2": flat_row["smps2"],
            "battery": flat_row["battery"],
            "current_limit": flat_row["current_limit"],
            "critical_current": flat_row["critical_current"],
            "critical_power": flat_row["critical_power"],
            "hospital_current": flat_row["hospital_current"],
            "hospital_power": flat_row["hospital_power"],
            "hospital_relay": flat_row["hospital_relay"],
            "street_current": flat_row["street_current"],
            "street_power": flat_row["street_power"],
            "street_relay": flat_row["street_relay"],
            "house_current": flat_row["house_current"],
            "house_power": flat_row["house_power"],
            "house_relay": flat_row["house_relay"],
            "industry_current": flat_row["industry_current"],
            "industry_power": flat_row["industry_power"],
            "industry_relay": flat_row["industry_relay"],
            "total_current": flat_row["total_current"],
            "total_power": flat_row["total_power"]
        }

        # Lags
        def get_lag(col, steps):
            if len(df_hist) > steps and col in df_hist.columns:
                return float(df_hist[col].iloc[-(steps + 1)])
            return float(flat_row.get(col, 0.0))

        features["total_current_lag_1"] = get_lag("total_current", 1)
        features["total_current_lag_3"] = get_lag("total_current", 3)
        features["total_current_lag_6"] = get_lag("total_current", 6)
        features["total_current_lag_30"] = get_lag("total_current", 30)

        # Rolling averages
        if "total_current" in df_hist.columns:
            features["total_current_avg_1min"] = float(df_hist["total_current"].iloc[-6:].mean())
            features["total_current_avg_5min"] = float(df_hist["total_current"].iloc[-30:].mean())
            features["total_current_avg"] = float(df_hist["total_current"].iloc[-6:].mean())
        else:
            features["total_current_avg_1min"] = flat_row["total_current"]
            features["total_current_avg_5min"] = flat_row["total_current"]
            features["total_current_avg"] = flat_row["total_current"]

        if "total_power" in df_hist.columns:
            features["total_power_avg_1min"] = float(df_hist["total_power"].iloc[-6:].mean())
            features["total_power_avg_5min"] = float(df_hist["total_power"].iloc[-30:].mean())
        else:
            features["total_power_avg_1min"] = flat_row["total_power"]
            features["total_power_avg_5min"] = flat_row["total_power"]

        # Rates
        def get_rate(col):
            if len(df_hist) > 1 and col in df_hist.columns:
                return float(df_hist[col].iloc[-1] - df_hist[col].iloc[-2])
            return 0.0

        features["total_current_rate"] = get_rate("total_current")
        features["load_utilization"] = (
            flat_row["total_current"] / flat_row["current_limit"]
            if flat_row["current_limit"] > 0 else 0.0
        )

        for load in ["hospital", "street", "house", "industry"]:
            if f"{load}_current" in df_hist.columns:
                features[f"{load}_current_avg"] = float(df_hist[f"{load}_current"].iloc[-6:].mean())
            else:
                features[f"{load}_current_avg"] = flat_row[f"{load}_current"]
            features[f"{load}_current_rate"] = get_rate(f"{load}_current")

        return features

    def run_inference_and_diagnostics(self, flat_row: dict, commanded_relays: dict, tripped_relays: set, stuck_relays: set) -> dict:
        flat_row = self.ensure_flat_row(flat_row)
        features = self.compute_features(flat_row)
        faults_list = []
        branch_diagnostics = {}
        loads = ["hospital", "street", "house", "industry"]

        # 1. Branch-level ML diagnostic classification
        for load in loads:
            model_key = f"model_{load}"
            status_pred = "NORMAL"

            if model_key in self.models:
                try:
                    m_obj = self.models[model_key]
                    clf = m_obj["model"]
                    feat_cols = m_obj["features"]
                    branch_data = {
                        f"{load}_v": flat_row[f"{load}_voltage"],
                        f"{load}_ma": flat_row[f"{load}_current"],
                        f"{load}_mw": flat_row[f"{load}_power"],
                        f"{load}_relay": flat_row[f"{load}_relay"],
                        "critical_v": flat_row["critical_voltage"],
                        "critical_ma": flat_row["critical_current"],
                        "total_current": flat_row["total_current"],
                        "total_power": flat_row["total_power"],
                        "smps1": flat_row["smps1"],
                        "smps2": flat_row["smps2"],
                        "battery": flat_row["battery"]
                    }
                    df_b = pd.DataFrame([branch_data])[feat_cols]
                    status_pred = str(clf.predict(df_b)[0])
                except Exception as e:
                    status_pred = "NORMAL"
            else:
                relay = flat_row[f"{load}_relay"]
                curr = flat_row[f"{load}_current"]
                thresh = config.thresh_2sd[load]
                if relay == 0 and curr > 25.0:
                    status_pred = "RELAY_OFF_CURRENT_DRAWN"
                elif relay == 1 and curr < 10.0:
                    status_pred = "RELAY_ON_NO_CURRENT"
                elif relay == 1 and curr > thresh:
                    status_pred = "OVERCURRENT"
                elif relay == 1 and curr < (0.60 * config.nominal_draws[load]):
                    status_pred = "UNDERCURRENT"

            branch_diagnostics[load] = status_pred
            if status_pred != "NORMAL":
                faults_list.append({
                    "load": load.upper(),
                    "type": status_pred,
                    "severity": "HIGH" if status_pred in ["OVERCURRENT", "RELAY_OFF_CURRENT_DRAWN"] else "MEDIUM"
                })

        # Critical Load Diagnosis
        crit_curr = flat_row["critical_current"]
        crit_volt = flat_row["critical_voltage"]
        crit_status = "NORMAL"
        if crit_curr > config.thresh_2sd["critical"]:
            crit_status = "OVERCURRENT"
            faults_list.append({"load": "CRITICAL", "type": "OVERCURRENT", "severity": "HIGH"})
        elif crit_curr < 15.0 and crit_volt > 10.0:
            crit_status = "OPEN_CIRCUIT"
            faults_list.append({"load": "CRITICAL", "type": "OPEN_CIRCUIT", "severity": "HIGH"})
        branch_diagnostics["critical"] = crit_status

        # 2. Dynamic load-aware & fault-aware load prediction breakdown
        loads_on_count = 0
        healthy_loads_count = 0
        total_pred_current = 0.0
        total_pred_power = 0.0
        pred_breakdown = {}

        for load in loads:
            relay = flat_row.get(f"{load}_relay", 1)
            cmd = commanded_relays.get(load, 1)
            # A load is physically and logically ON only if both relay is closed and it is commanded ON
            is_on = (relay == 1 and cmd == 1) and (load not in tripped_relays)
            diag = branch_diagnostics.get(load, "NORMAL")
            curr = flat_row[f"{load}_current"]
            volt = flat_row[f"{load}_voltage"]

            if is_on:
                loads_on_count += 1
                if diag == "NORMAL":
                    healthy_loads_count += 1
                    # If drawing current, use measured current; if < 15mA, load is physically unplugged/open
                    b_pred_i = curr if curr >= 15.0 else 0.0
                    reason = "ON & Operating (Fault-Free)" if curr >= 15.0 else "ON (No Load / Open)"
                    is_h = True
                elif "NO_CURRENT" in diag or "OPEN" in diag:
                    b_pred_i = curr
                    reason = "ON with FAULT (No Current)"
                    is_h = False
                elif "OVERCURRENT" in diag:
                    b_pred_i = 0.0
                    reason = "ON with OVERCURRENT (Projected Trip/Shed)"
                    is_h = False
                else:
                    b_pred_i = curr
                    reason = f"Active Fault ({diag})"
                    is_h = False
            else:
                if load in stuck_relays or diag == "RELAY_OFF_CURRENT_DRAWN" or (relay == 0 and curr > 25.0):
                    b_pred_i = curr
                    reason = "OFF but STUCK CLOSED (Welded Contacts)"
                    is_h = False
                else:
                    b_pred_i = 0.0
                    reason = "Commanded OFF (Standby)"
                    is_h = True

            b_pred_p = (b_pred_i * (volt if volt > 1.0 else 12.0)) / 1000.0
            total_pred_current += b_pred_i
            total_pred_power += b_pred_p

            pred_breakdown[load] = {
                "name": load.capitalize(),
                "on": 1 if (is_on and curr >= 15.0) else (1 if is_on else 0),
                "status": diag,
                "is_healthy": is_h,
                "predicted_current": round(b_pred_i, 1),
                "predicted_power": round(b_pred_p, 2),
                "reason": reason
            }

        # Critical Load in prediction
        loads_on_count += 1
        if crit_status == "NORMAL":
            healthy_loads_count += 1
            crit_pred_i = crit_curr if crit_curr >= 20.0 else 300.0
            crit_reason = "Fixed Infrastructure (Normal)"
            crit_h = True
        else:
            crit_pred_i = crit_curr
            crit_reason = f"Critical Fault ({crit_status})"
            crit_h = False

        crit_pred_p = (crit_pred_i * (crit_volt if crit_volt > 1.0 else 12.0)) / 1000.0
        total_pred_current += crit_pred_i
        total_pred_power += crit_pred_p
        pred_breakdown["critical"] = {
            "name": "Critical",
            "on": 1,
            "status": crit_status,
            "is_healthy": crit_h,
            "predicted_current": round(crit_pred_i, 1),
            "predicted_power": round(crit_pred_p, 2),
            "reason": crit_reason
        }

        # 3. Forecast Regressor Inference (Model 1A / 1B)
        reg_pred_curr = None
        reg_pred_pow = None
        if "forecaster_current" in self.models and "forecasting_features" in self.feature_headers:
            try:
                cols = self.feature_headers["forecasting_features"]
                aligned = {}
                for c in cols:
                    if c.startswith("mode_"):
                        m_name = c.replace("mode_", "")
                        aligned[c] = 1.0 if features["mode"] == m_name else 0.0
                    else:
                        aligned[c] = float(features.get(c, 0.0))
                df_f = pd.DataFrame([aligned])[cols]
                reg_pred_curr = float(self.models["forecaster_current"].predict(df_f)[0])
                if "forecaster_power" in self.models:
                    raw_pow = float(self.models["forecaster_power"].predict(df_f)[0])
                    # Trained model outputs milliwatts; normalize to Watts for the dashboard
                    reg_pred_pow = (raw_pow / 1000.0) if raw_pow > 100 else raw_pow
            except Exception:
                pass

        # Final predictions: Hybrid Physics-Constrained ML Forecasting
        # When loads are shed or switched off, the statistical RF regressor cannot violate Kirchhoff's laws
        # by predicting load for disconnected circuits.
        if loads_on_count <= 1:
            # 0 normal loads active (only critical load is running)
            final_pred_i = round(total_pred_current, 1)
            final_pred_p = round(total_pred_power, 2)
        else:
            if reg_pred_curr is not None:
                final_pred_i = round(min(reg_pred_curr, total_pred_current * 1.18), 1)
                final_pred_i = max(final_pred_i, round(total_pred_current * 0.82, 1))
            else:
                final_pred_i = round(total_pred_current, 1)

            if reg_pred_pow is not None:
                final_pred_p = round(min(reg_pred_pow, total_pred_power * 1.18), 2)
                final_pred_p = max(final_pred_p, round(total_pred_power * 0.82, 2))
            else:
                final_pred_p = round(total_pred_power, 2)

        fault_detected = 1 if len(faults_list) > 0 else 0
        fault_load = ", ".join([f["load"] for f in faults_list]) if fault_detected else "NONE"
        fault_type = ", ".join([f["type"] for f in faults_list]) if fault_detected else "NORMAL"
        severity = "HIGH" if any(f["severity"] == "HIGH" for f in faults_list) else ("MEDIUM" if fault_detected else "NONE")

        result = flat_row.copy()
        result["predicted_current"] = final_pred_i
        result["predicted_power"] = final_pred_p
        result["regressor_predicted_current"] = round(reg_pred_curr, 1) if reg_pred_curr else final_pred_i
        result["regressor_predicted_power"] = round(reg_pred_pow, 2) if reg_pred_pow else final_pred_p
        result["loads_on_count"] = loads_on_count
        result["healthy_loads_count"] = healthy_loads_count
        result["prediction_breakdown"] = pred_breakdown
        result["fault_detected"] = fault_detected
        result["fault_load"] = fault_load
        result["fault_type"] = fault_type
        result["severity"] = severity
        result["branch_diagnostics"] = branch_diagnostics

        return result

ml_engine = MLEngine()
