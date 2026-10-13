import time
import json
import threading
import datetime
try:
    from core.config import config
    from core.mqtt_client import ResilientMQTTClient
except ImportError:
    from src.core.config import config
    from src.core.mqtt_client import ResilientMQTTClient

class MockESP32Simulator:
    """
    High-fidelity physical hardware simulator that mimics the real ESP32 firmware:
    - Generates 2.0-second JSON telemetry packets matching smartgrid/live schema
    - Subscribes to smartgrid/control to emulate physical relay actuation (Active LOW)
    - Supports dynamic scenario transitions (Dual SMPS -> Single SMPS, Overcurrent, Shedding, Headroom Packing)
    """
    def __init__(self):
        self.running = False
        self.mode = "DUAL SMPS"
        self.current_limit = 5000.0
        self.smps1 = True
        self.smps2 = True
        self.battery = False

        self.relays = {
            "hospital": 1,
            "street": 1,
            "house": 1,
            "industry": 1
        }

        self.client = ResilientMQTTClient(client_id=f"MOCK_ESP32_{int(time.time())}")
        self.client.on_control_callback = self._on_control_command

    def _on_control_command(self, payload: dict):
        cmd = payload.get("cmd", "")
        load = payload.get("load", "").lower()
        state = payload.get("state", None)
        reason = payload.get("reason", "")

        if state in (0, 1) and load in self.relays:
            self.relays[load] = state
            print(f"  🤖 [MOCK ESP32 ACTUATED] Relay {load.upper()} -> {'ON' if state == 1 else 'OFF'} (Reason: {reason})")

    def generate_packet(self) -> dict:
        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Nominal currents
        c_crit = 298.5
        v_crit = 12.04

        # Draws based on relay states
        c_hosp = 252.0 if self.relays["hospital"] == 1 else 0.0
        c_str = 391.0 if self.relays["street"] == 1 else 0.0
        c_hou = 238.0 if self.relays["house"] == 1 else 0.0
        c_ind = 236.0 if self.relays["industry"] == 1 else 0.0

        tot_i = c_crit + c_hosp + c_str + c_hou + c_ind
        tot_p = (tot_i * 12.02)

        return {
            "timestamp": now_ts,
            "device_id": "ESP32_SIMULATOR",
            "firmware": "2.0.0-simulated",
            "hardware": "ESP32_VIRTUAL",
            "location": "Virtual Lab",
            "group": "Group A",
            "wifi_rssi": -55,
            "uptime": int(time.time()),
            "mode": self.mode,
            "current_limit": self.current_limit,
            "sources": {
                "smps1": self.smps1,
                "smps2": self.smps2,
                "battery": self.battery
            },
            "critical": {
                "voltage": v_crit,
                "current": c_crit,
                "power": c_crit * v_crit
            },
            "loads": [
                {"name": "Hospital", "voltage": 12.02, "current": c_hosp, "power": c_hosp * 12.02, "relay": bool(self.relays["hospital"]), "priority": 4, "fault": 0, "nominal_current": 256.0},
                {"name": "Street", "voltage": 12.01, "current": c_str, "power": c_str * 12.01, "relay": bool(self.relays["street"]), "priority": 3, "fault": 0, "nominal_current": 394.0},
                {"name": "House", "voltage": 12.03, "current": c_hou, "power": c_hou * 12.03, "relay": bool(self.relays["house"]), "priority": 2, "fault": 0, "nominal_current": 241.0},
                {"name": "Industry", "voltage": 12.00, "current": c_ind, "power": c_ind * 12.00, "relay": bool(self.relays["industry"]), "priority": 1, "fault": 0, "nominal_current": 240.0}
            ],
            "totals": {
                "current": tot_i,
                "power": tot_p
            }
        }

    def start_simulation(self):
        self.running = True
        self.client.start()
        time.sleep(2.0)  # Await connection

        def loop():
            step = 0
            while self.running:
                step += 1
                # Scenario transitions demonstration:
                # Steps 1-15: Dual SMPS boot (5000mA limit)
                # Step 16+: Drop to Single SMPS (1000mA limit) to test shedding & priority packing
                if step == 16:
                    print("\n>>> [SIMULATION EVENT] Grid Main SMPS2 Tripped! Switching to Single SMPS (1000mA limit) <<<")
                    self.mode = "SINGLE SMPS"
                    self.current_limit = 1000.0
                    self.smps2 = False

                packet = self.generate_packet()
                self.client.publish_telemetry(packet)
                time.sleep(config.update_interval_sec)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def stop_simulation(self):
        self.running = False
        self.client.stop()
