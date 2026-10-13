import os
from dataclasses import dataclass, field
from typing import Dict

def load_dotenv(env_path: str):
    """Simple, robust .env parser without external dependencies."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"[Config] Warning: Failed to parse .env file: {e}")

# Discover Project Root (3 levels up from src/core/config.py)
CURRENT_FILE = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_FILE)))
if not os.path.exists(os.path.join(PROJECT_ROOT, "models")):
    # Fallback if structure varies
    PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_FILE))

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(ENV_PATH)

@dataclass
class GridConfig:
    # MQTT
    mqtt_broker: str = os.getenv("MQTT_BROKER", "78d11d43ac27466695cd0e4f5e7405c8.s1.eu.hivemq.cloud")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "8883"))
    mqtt_user: str = os.getenv("MQTT_USER", "saptarshidas")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "saptarshi2007")
    mqtt_topic_live: str = os.getenv("MQTT_TOPIC_LIVE", "smartgrid/live")
    mqtt_topic_control: str = os.getenv("MQTT_TOPIC_CONTROL", "smartgrid/control")

    # Telegram
    telegram_enabled: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "8948721490:AAFuwXc-P22Cqy_Br6o0xzbECSWYkOXuQcg")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "7944457244")
    telegram_send_status: bool = os.getenv("TELEGRAM_SEND_STATUS_CARDS", "true").lower() in ("true", "1", "yes")

    # SCADA Server
    scada_host: str = os.getenv("SCADA_HOST", "0.0.0.0")
    scada_port: int = int(os.getenv("SCADA_PORT", "8000"))

    # Timing & Intervals
    update_interval_sec: float = float(os.getenv("UPDATE_INTERVAL_SEC", "2.0"))
    startup_observe_sec: float = float(os.getenv("STARTUP_OBSERVE_SEC", "30.0"))
    relay_settling_sec: float = float(os.getenv("RELAY_SETTLING_SEC", "15.0"))
    restoration_settling_sec: float = float(os.getenv("RESTORATION_SETTLING_SEC", "15.0"))

    # Capacity Thresholds (%)
    max_restore_util_pct: float = float(os.getenv("MAX_RESTORE_UTIL_PCT", "84.0"))
    shed_util_pct: float = float(os.getenv("SHED_UTIL_PCT", "85.0"))
    high_load_util_pct: float = float(os.getenv("HIGH_LOAD_UTIL_PCT", "80.0"))
    medium_load_util_pct: float = float(os.getenv("MEDIUM_LOAD_UTIL_PCT", "70.0"))

    # Hardware Statistical 2-SD Overcurrent Limits (mA)
    thresh_2sd: Dict[str, float] = field(default_factory=lambda: {
        "critical": 320.0,
        "hospital": 272.0,
        "street": 405.0,
        "house": 256.0,
        "industry": 264.0
    })

    # Nominal hardware draws (mA) for headroom calculations
    nominal_draws: Dict[str, float] = field(default_factory=lambda: {
        "hospital": 256.0,
        "street": 394.0,
        "house": 241.0,
        "industry": 240.0,
        "critical": 300.0
    })

    # Shedding Priorities (Lowest sheds first)
    load_priorities: Dict[str, int] = field(default_factory=lambda: {
        "critical": 5,
        "hospital": 4,
        "street": 3,
        "house": 2,
        "industry": 1
    })

    # Paths
    script_dir: str = PROJECT_ROOT
    project_root: str = PROJECT_ROOT
    db_path: str = os.path.join(PROJECT_ROOT, "live_smartgrid.db")
    models_dir: str = os.path.join(PROJECT_ROOT, "models")
    reports_dir: str = os.path.join(PROJECT_ROOT, "results")
    data_dir: str = os.path.join(PROJECT_ROOT, "data", "raw")

config = GridConfig()
