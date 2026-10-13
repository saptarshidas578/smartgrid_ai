import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root is in path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
for p in [PROJECT_ROOT, SRC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from services.safety_engine import SafetyEngine
    from core.config import config
except ImportError:
    from src.services.safety_engine import SafetyEngine
    from src.core.config import config

def test_instant_overcurrent_trip():
    print("\n--- TEST 1: Instant 2-SD Overcurrent Protection ---")
    engine = SafetyEngine()
    dispatched_commands = []
    def mock_publish(cmd):
        dispatched_commands.append(cmd)

    # Simulate hospital current > 272.0 mA
    sample_row = {
        "timestamp": "2026-09-16 12:00:00",
        "current_limit": 5000.0,
        "total_current": 800.0,
        "critical_current": 300.0,
        "hospital_current": 290.0,  # Exceeds 272.0 mA limit
        "street_current": 100.0,
        "house_current": 100.0,
        "industry_current": 100.0
    }

    in_startup, remaining, action = engine.evaluate_telemetry(sample_row, mock_publish)
    assert "hospital" in engine.tripped_relays, "Hospital should be marked as TRIPPED!"
    assert engine.commanded_relays["hospital"] == 0, "Hospital relay should be commanded OFF!"
    assert len(dispatched_commands) == 1, "Should dispatch exactly 1 TRIP command!"
    assert dispatched_commands[0]["cmd"] == "TRIP", "Command must be TRIP!"
    assert dispatched_commands[0]["load"] == "hospital"
    print("  [PASS] Instant overcurrent trip verified successfully!")

def test_observation_window_suppresses_capacity_shedding():
    print("\n--- TEST 2: 30s Startup Observation Window ---")
    engine = SafetyEngine()
    dispatched_commands = []
    def mock_publish(cmd):
        dispatched_commands.append(cmd)

    # 90% load utilization (900mA / 1000mA), but within 30s boot window
    sample_row = {
        "timestamp": "2026-09-16 12:00:01",
        "current_limit": 1000.0,
        "total_current": 900.0,  # 90% >= 85%
        "critical_current": 250.0,
        "hospital_current": 200.0,
        "street_current": 200.0,
        "house_current": 150.0,
        "industry_current": 100.0
    }

    in_startup, remaining, action = engine.evaluate_telemetry(sample_row, mock_publish)
    assert in_startup is True, "Must be in startup observation!"
    assert len(dispatched_commands) == 0, "Capacity shedding MUST be suppressed during 30s observation phase!"
    print("  [PASS] Observation phase suppression verified successfully!")

def test_priority_shedding():
    print("\n--- TEST 3: Priority Shedding (>85% Overload) ---")
    engine = SafetyEngine()
    # Fast-forward startup window
    engine.system_start_time = time.time() - 35.0
    for l in engine.commanded_relays:
        engine.relay_turn_on_time[l] = time.time() - 20.0  # Settled > 15s

    dispatched_commands = []
    def mock_publish(cmd):
        dispatched_commands.append(cmd)

    # 88% load utilization (880mA / 1000mA Single SMPS)
    sample_row = {
        "timestamp": "2026-09-16 12:00:35",
        "current_limit": 1000.0,
        "total_current": 880.0,  # 88% >= 85%
        "critical_current": 250.0,
        "hospital_current": 200.0,
        "street_current": 200.0,
        "house_current": 130.0,
        "industry_current": 100.0
    }

    in_startup, remaining, action = engine.evaluate_telemetry(sample_row, mock_publish)
    assert in_startup is False
    assert len(dispatched_commands) == 1, "Should dispatch 1 SHED command!"
    assert dispatched_commands[0]["cmd"] == "SHED"
    assert dispatched_commands[0]["load"] == "industry", "Industry (priority 1) must shed first!"
    assert engine.commanded_relays["industry"] == 0
    print("  [PASS] Lowest-priority load (Industry) shed first as expected!")

def test_priority_packing_restoration():
    print("\n--- TEST 4: Opportunistic Priority Packing (<84% Headroom) ---")
    engine = SafetyEngine()
    now = time.time()
    engine.system_start_time = now - 60.0
    engine.last_shed_time = now - 20.0
    engine.last_restored_time = now - 20.0
    engine.last_mode_transition_time = now - 20.0

    # House and Industry are OFF (settled > 15s)
    engine.commanded_relays = {"hospital": 1, "street": 1, "house": 0, "industry": 0}
    engine.relay_turn_off_time = {"hospital": 0.0, "street": 0.0, "house": now - 25.0, "industry": now - 25.0}

    dispatched_commands = []
    def mock_publish(cmd):
        dispatched_commands.append(cmd)

    # Current limit: 1000 mA. Current total: 580 mA (58% utilization).
    # Remaining headroom to 84%: 840 mA - 580 mA = 260 mA.
    # House (priority 2) nominal draw: 241 mA.
    # 580 + 241 = 821 mA = 82.1% <= 84.0% -> FITS!
    sample_row = {
        "timestamp": "2026-09-16 12:01:00",
        "current_limit": 1000.0,
        "total_current": 580.0,
        "critical_current": 280.0,
        "hospital_current": 200.0,
        "street_current": 100.0,
        "house_current": 0.0,
        "industry_current": 0.0
    }

    in_startup, remaining, action = engine.evaluate_telemetry(sample_row, mock_publish)
    assert len(dispatched_commands) == 1, "Should restore 1 candidate!"
    assert dispatched_commands[0]["cmd"] == "RESTORE"
    assert dispatched_commands[0]["load"] == "house", "House should be restored (priority 2 > priority 1)!"
    assert engine.commanded_relays["house"] == 1
    print("  [PASS] House restored under priority packing headroom <= 84%!")

def run_all_tests():
    print("=" * 60)
    print("  [TEST SUITE] RUNNING COMPREHENSIVE SAFETY ENGINE TESTS")
    print("=" * 60)
    test_instant_overcurrent_trip()
    test_observation_window_suppresses_capacity_shedding()
    test_priority_shedding()
    test_priority_packing_restoration()
    print("\n" + "=" * 60)
    print("  [SUCCESS] ALL SAFETY ENGINE TESTS PASSED (100%)")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
