import os
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", message=r".*sklearn\.utils\.parallel.*")
import time
import json
import datetime
import paho.mqtt.client as mqtt

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURRENT_FILE = os.path.abspath(__file__)
SRC_DIR = os.path.dirname(CURRENT_FILE)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
for p in [PROJECT_ROOT, SRC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from core.config import config
    from core.database import db
    from services.ml_engine import ml_engine
    from services.safety_engine import safety_engine
    from services.telegram_service import telegram
except ImportError:
    from src.core.config import config
    from src.core.database import db
    from src.services.ml_engine import ml_engine
    from src.services.safety_engine import safety_engine
    from src.services.telegram_service import telegram

SCRIPT_DIR = PROJECT_ROOT

mqtt_client = None

def on_connect(client, userdata, flags, rc, *args):
    if rc == 0:
        print("\n[MQTT] Connected to HiveMQ Cloud broker successfully!")
        client.subscribe([(config.mqtt_topic_live, 0), (config.mqtt_topic_control, 1)])
        print(f"[MQTT] Subscribed to telemetry: {config.mqtt_topic_live}")
        print(f"[MQTT] Subscribed to closed-loop actuator: {config.mqtt_topic_control}")
    else:
        print(f"[MQTT] Connection failed with error code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode("utf-8"))

        if topic == config.mqtt_topic_live:
            data = payload.get("data", payload)
            if not isinstance(data, dict):
                return

            # 1. Flatten & clean telemetry
            flat_row = ml_engine.flatten_raw_telemetry(data)

            # 2. Run real-time ML feature engineering & inference
            pred_row = ml_engine.run_inference_and_diagnostics(
                flat_row,
                commanded_relays=safety_engine.commanded_relays,
                tripped_relays=safety_engine.tripped_relays,
                stuck_relays=safety_engine.stuck_relays
            )

            # 3. Publish function callback for safety engine
            def publish_actuator_cmd(cmd_payload):
                client.publish(config.mqtt_topic_control, json.dumps(cmd_payload), qos=1)

            # 4. Evaluate closed-loop safety actions (2-SD trip, shed, priority pack)
            in_startup, startup_rem, action_taken = safety_engine.evaluate_telemetry(pred_row, publish_actuator_cmd)

            # 5. Persist to SQLite WAL database
            db.log_telemetry(pred_row)

            # 6. Render live console dashboard
            print_ascii_dashboard(pred_row, in_startup, startup_rem, action_taken)

        elif topic == config.mqtt_topic_control:
            cmd = payload.get("cmd", "")
            load = payload.get("load", "")
            state = payload.get("state", None)
            reason = payload.get("reason", "")
            if state in (0, 1) and load in safety_engine.commanded_relays:
                safety_engine.commanded_relays[load] = state
                if state == 1:
                    safety_engine.relay_turn_on_time[load] = time.time()
                    safety_engine.tripped_relays.discard(load)
                else:
                    safety_engine.relay_turn_off_time[load] = time.time()

    except Exception as e:
        print(f"[AI Loop Error] {e}")

def print_ascii_dashboard(row: dict, in_startup: bool, startup_rem: float, action_taken: str):
    limit = float(row.get("current_limit", 5000.0))
    tot_curr = float(row.get("total_current", 0.0))
    utilization = (tot_curr / limit * 100.0) if limit > 0 else 0.0

    print("\n" + "=" * 80)
    print("           ⚡ SMART GRID REAL-TIME AUTONOMOUS AI CONTROLLER ⚡")
    print("=" * 80)

    # Check for public link
    link_file = os.path.join(SCRIPT_DIR, "public_link.txt")
    if os.path.exists(link_file):
        try:
            with open(link_file, "r") as f:
                pub = f.read().strip()
                if pub:
                    print(f" 🌐 GLOBAL SCADA LINK : {pub}")
                    print(f" 🏠 LOCAL WI-FI LINK  : http://localhost:8000")
                    print("-" * 80)
        except Exception:
            pass

    print(f" Timestamp: {row['timestamp']} | Interval: {config.update_interval_sec:.0f}s | Mode: {row['mode']} | Limit: {limit:.0f} mA")
    print(f" Control Mode: {safety_engine.control_mode} | Health: {row.get('severity', 'NONE')} | Fault: {row.get('fault_type', 'NORMAL')}")
    print("-" * 80)
    tot_pow_w = (tot_curr * 12.0) / 1000.0
    print(f" TOTAL LOAD : {tot_curr:6.1f} mA ({tot_pow_w:5.2f} W) / {limit:.0f} mA  [{utilization:5.1f}% UTILIZATION]")
    print(f" PREDICTED  : {row.get('predicted_current', 0.0):6.1f} mA (AI Pred Power: {row.get('predicted_power', 0.0):5.2f} W)")

    # Status Bar
    bar_len = 35
    filled = int(min(utilization, 100.0) / 100.0 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f" CAPACITY   : [{bar}] {utilization:5.1f}%")
    print("-" * 80)

    # Branch breakdown table
    print(" SECTOR       | STATUS     | RELAY | CURRENT (mA) | ACTIVE (W) | PREDICTED  | 2-SD LIMIT")
    print(" ------------ | ---------- | ----- | ------------ | ---------- | ---------- | ----------")
    crit_c = float(row.get("critical_current", 300.0))
    crit_p = (crit_c * 12.0) / 1000.0
    crit_diag = row.get("branch_diagnostics", {}).get("critical", "NORMAL")
    print(f" CRITICAL     | {crit_diag:<10} | PERM  | {crit_c:10.1f}   | {crit_p:7.2f} W  |   {crit_c:6.1f}   |   {config.thresh_2sd['critical']:.0f} mA")

    for l in ["hospital", "street", "house", "industry"]:
        diag = row.get("branch_diagnostics", {}).get(l, "NORMAL")
        r_state = "ON" if safety_engine.commanded_relays.get(l, 1) == 1 else "OFF"
        c_val = float(row.get(f"{l}_current", 0.0))
        p_act_w = (c_val * 12.0) / 1000.0 if (r_state == "ON" and c_val >= 15.0) else 0.0
        p_val = row.get("prediction_breakdown", {}).get(l, {}).get("predicted_current", 0.0)
        lim_val = config.thresh_2sd[l]
        print(f" {l.upper():<12} | {diag:<10} | {r_state:<5} | {c_val:10.1f}   | {p_act_w:7.2f} W  |   {p_val:6.1f}   |   {lim_val:.0f} mA")

    print("-" * 80)
    if in_startup:
        print(f" ⏳ STARTUP PHASE: Initial Observation Window Active ({startup_rem:.0f}s remaining)")
    elif action_taken:
        print(f" ⚡ LAST ACTION : {action_taken}")
    else:
        print(f" 🟢 GRID STATUS : {row.get('warning_message', 'NORMAL')}")
    print("=" * 80)

def start_ai_controller():
    global mqtt_client
    print("\n==================================================================")
    print("     ⚡ AUTONOMOUS SMART GRID AI CLOSED-LOOP ENGINE INITIALIZED ⚡")
    print("==================================================================")
    print(f" Broker  : {config.mqtt_broker}:{config.mqtt_port}")
    print(f" Database: {config.db_path} (WAL Mode Active)")
    print(f" Safety  : 15s Anti-Chattering Dwell | Priority Packing <= 84%")
    print("==================================================================\n")

    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        mqtt_client = mqtt.Client()

    mqtt_client.username_pw_set(config.mqtt_user, config.mqtt_password)
    mqtt_client.tls_set()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    start_ai_controller()
