import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
for p in [PROJECT_ROOT, SRC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from services.ml_engine import ml_engine
    from core.config import config
except ImportError:
    from src.services.ml_engine import ml_engine
    from src.core.config import config

def test_telemetry_flattening():
    print("\n--- TEST 1: Telemetry Flattening & Sensor Drift Clamping ---")
    raw_packet = {
        "timestamp": "2026-09-16 12:00:00",
        "device_id": "ESP32_TEST",
        "mode": "SINGLE SMPS",
        "current_limit": 1000.0,
        "sources": {"smps1": True, "smps2": False, "battery": False},
        "critical": {"voltage": 12.05, "current": 298.0, "power": 3590.9},
        "loads": [
            {"name": "Hospital", "voltage": 12.02, "current": -0.6, "power": -7.2, "relay": True},
            {"name": "Street", "voltage": 12.01, "current": 390.0, "power": 4683.9, "relay": True},
            {"name": "House", "voltage": 12.03, "current": 240.0, "power": 2887.2, "relay": True},
            {"name": "Industry", "voltage": 12.00, "current": 0.0, "power": 0.0, "relay": False}
        ],
        "totals": {"current": 928.0, "power": 11162.0}
    }

    flat = ml_engine.flatten_raw_telemetry(raw_packet)
    assert flat["mode"] == "SINGLE SMPS"
    assert flat["current_limit"] == 1000.0
    assert flat["hospital_current"] == 0.0, "Negative sensor reading must be clamped to 0.0 mA!"
    assert flat["street_current"] == 390.0
    assert flat["hospital_relay"] == 1
    assert flat["industry_relay"] == 0
    print("  [PASS] Telemetry flattening and clamping verified successfully!")

def test_rolling_feature_calculation():
    print("\n--- TEST 2: In-Memory Rolling Feature Calculation ---")
    # Feed 10 sequential frames
    for i in range(10):
        dummy_row = {
            "timestamp": f"2026-09-16 12:00:{i*2:02d}",
            "device_id": "ESP32_TEST",
            "mode": "SINGLE SMPS",
            "current_limit": 1000.0,
            "smps1": 1, "smps2": 0, "battery": 0,
            "critical_voltage": 12.0, "critical_current": 300.0, "critical_power": 3600.0,
            "hospital_voltage": 12.0, "hospital_current": 250.0, "hospital_power": 3000.0, "hospital_relay": 1, "hospital_priority": 4, "hospital_nominal_current": 256.0,
            "street_voltage": 12.0, "street_current": 390.0, "street_power": 4680.0, "street_relay": 1, "street_priority": 3, "street_nominal_current": 394.0,
            "house_voltage": 12.0, "house_current": 240.0, "house_power": 2880.0, "house_relay": 1, "house_priority": 2, "house_nominal_current": 241.0,
            "industry_voltage": 12.0, "industry_current": 0.0, "industry_power": 0.0, "industry_relay": 0, "industry_priority": 1, "industry_nominal_current": 240.0,
            "total_current": 1180.0, "total_power": 14160.0
        }
        feats = ml_engine.compute_features(dummy_row)

    assert "total_current_lag_1" in feats
    assert "total_current_avg_1min" in feats
    assert "total_current_rate" in feats
    assert feats["load_utilization"] == 1.18
    print("  [PASS] Rolling feature calculation verified successfully!")

def test_inference_diagnostics_and_predictions():
    print("\n--- TEST 3: Model Inference & Dynamic Prediction Synthesis ---")
    dummy_flat = {
        "timestamp": "2026-09-16 12:00:20",
        "device_id": "ESP32_TEST",
        "mode": "DUAL SMPS",
        "current_limit": 5000.0,
        "smps1": 1, "smps2": 1, "battery": 0,
        "critical_voltage": 12.0, "critical_current": 298.0, "critical_power": 3576.0,
        "hospital_voltage": 12.0, "hospital_current": 252.0, "hospital_power": 3024.0, "hospital_relay": 1, "hospital_priority": 4, "hospital_nominal_current": 256.0,
        "street_voltage": 12.0, "street_current": 392.0, "street_power": 4704.0, "street_relay": 1, "street_priority": 3, "street_nominal_current": 394.0,
        "house_voltage": 12.0, "house_current": 238.0, "house_power": 2856.0, "house_relay": 1, "house_priority": 2, "house_nominal_current": 241.0,
        "industry_voltage": 12.0, "industry_current": 235.0, "industry_power": 2820.0, "industry_relay": 1, "industry_priority": 1, "industry_nominal_current": 240.0,
        "total_current": 1415.0, "total_power": 16980.0
    }

    t0 = time.perf_counter()
    result = ml_engine.run_inference_and_diagnostics(
        dummy_flat,
        commanded_relays={"hospital": 1, "street": 1, "house": 1, "industry": 1},
        tripped_relays=set(),
        stuck_relays=set()
    )
    t1 = time.perf_counter()
    lat_ms = (t1 - t0) * 1000.0

    assert "predicted_current" in result
    assert "predicted_power" in result
    assert "prediction_breakdown" in result
    assert result["loads_on_count"] == 5  # 4 branch loads + 1 critical
    assert result["fault_detected"] == 0, "All branches normal, fault must be 0!"
    print(f"  [PASS] Inference completed in {lat_ms:.2f} ms with valid prediction breakdown!")

def run_all():
    print("=" * 60)
    print("  [TEST SUITE] RUNNING REAL-TIME ML PIPELINE TESTS")
    print("=" * 60)
    test_telemetry_flattening()
    test_rolling_feature_calculation()
    test_inference_diagnostics_and_predictions()
    print("\n" + "=" * 60)
    print("  [SUCCESS] ALL ML PIPELINE TESTS PASSED (100%)")
    print("=" * 60)

if __name__ == "__main__":
    run_all()
