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
    from core.config import config
    from core.database import db
    from services.ml_engine import ml_engine
    from services.safety_engine import safety_engine
    from services.mock_esp32 import MockESP32Simulator
except ImportError:
    from src.core.config import config
    from src.core.database import db
    from src.services.ml_engine import ml_engine
    from src.services.safety_engine import safety_engine
    from src.services.mock_esp32 import MockESP32Simulator

def test_e2e_pipeline_and_db_persistence():
    print("\n--- TEST 1: E2E Telemetry Ingestion -> ML Inference -> SQLite Persistence ---")
    sim = MockESP32Simulator()
    raw_packet = sim.generate_packet()

    # 1. Ingest & Flatten
    flat = ml_engine.flatten_raw_telemetry(raw_packet)
    assert flat["mode"] == "DUAL SMPS"

    # 2. ML Inference & Diagnostics
    pred_row = ml_engine.run_inference_and_diagnostics(
        flat,
        commanded_relays=safety_engine.commanded_relays,
        tripped_relays=safety_engine.tripped_relays,
        stuck_relays=safety_engine.stuck_relays
    )
    assert "predicted_current" in pred_row
    assert pred_row["fault_detected"] == 0

    # 3. Safety Evaluation
    dispatched = []
    def mock_publish(cmd):
        dispatched.append(cmd)

    in_start, rem, action = safety_engine.evaluate_telemetry(pred_row, mock_publish)

    # 4. Database Log
    success = db.log_telemetry(pred_row)
    assert success is True, "Database write must succeed!"

    # 5. Read back latest row
    latest = db.get_latest_telemetry()
    assert latest is not None
    assert latest["mode"] == "DUAL SMPS"
    print("  [PASS] E2E Ingestion, Inference, and Database Logging verified!")

def test_e2e_shed_and_actuation_audit():
    print("\n--- TEST 2: Overload -> Priority Shed -> Actuation Audit Trail ---")
    now = time.time()
    safety_engine.system_start_time = now - 40.0
    for l in safety_engine.commanded_relays:
        safety_engine.relay_turn_on_time[l] = now - 20.0

    # Simulate Single SMPS overload (890 mA / 1000 mA = 89% >= 85%)
    overload_row = {
        "timestamp": "2026-09-16 12:30:00",
        "current_limit": 1000.0,
        "total_current": 890.0,
        "critical_current": 250.0,
        "hospital_current": 200.0,
        "street_current": 200.0,
        "house_current": 140.0,
        "industry_current": 100.0
    }

    dispatched = []
    def mock_publish(cmd):
        dispatched.append(cmd)

    in_start, rem, action = safety_engine.evaluate_telemetry(overload_row, mock_publish)
    assert len(dispatched) == 1
    assert dispatched[0]["cmd"] == "SHED"
    assert dispatched[0]["load"] == "industry"

    events = db.get_recent_events(5)
    assert len(events) > 0
    assert events[0]["action_type"] == "SHED"
    assert events[0]["load_name"] == "industry"
    print("  [PASS] Shed event verified in database actuation audit trail!")

def run_all():
    print("=" * 60)
    print("  [TEST SUITE] RUNNING END-TO-END INTEGRATION TESTS")
    print("=" * 60)
    test_e2e_pipeline_and_db_persistence()
    test_e2e_shed_and_actuation_audit()
    print("\n" + "=" * 60)
    print("  [SUCCESS] ALL E2E INTEGRATION TESTS PASSED (100%)")
    print("=" * 60)

if __name__ == "__main__":
    run_all()
