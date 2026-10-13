import pytest
from src.core.config import config
from src.services.safety_engine import SafetyEngine

def test_config_thresholds_consistency():
    """Verify statistical 2-SD overcurrent thresholds exceed nominal ratings."""
    for load in ["hospital", "street", "house", "industry", "critical"]:
        assert load in config.thresh_2sd, f"Missing 2-SD threshold for {load}"
        assert load in config.nominal_draws, f"Missing nominal draw for {load}"
        # Threshold must be higher than nominal baseline to avoid false tripping
        assert config.thresh_2sd[load] > config.nominal_draws[load]

def test_load_priority_hierarchy():
    """Verify priority hierarchy values strictly order from 1 to 5."""
    assert config.load_priorities["critical"] == 5
    assert config.load_priorities["hospital"] == 4
    assert config.load_priorities["street"] == 3
    assert config.load_priorities["house"] == 2
    assert config.load_priorities["industry"] == 1

def test_safety_engine_initial_state():
    """Verify safety engine starts with all active loads commanded ON."""
    engine = SafetyEngine()
    for load in ["hospital", "street", "house", "industry"]:
        assert engine.commanded_relays[load] == 1
    assert len(engine.tripped_relays) == 0
    assert len(engine.stuck_relays) == 0
