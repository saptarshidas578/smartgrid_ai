import time
import json
import threading
from typing import Callable, Optional
import paho.mqtt.client as mqtt
try:
    from core.config import config
except ImportError:
    from src.core.config import config

class ResilientMQTTClient:
    def __init__(self,
                 broker: str = config.mqtt_broker,
                 port: int = config.mqtt_port,
                 username: str = config.mqtt_user,
                 password: str = config.mqtt_password,
                 client_id: Optional[str] = None):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id or f"SMARTGRID_HOST_{int(time.time())}"
        
        self.on_telemetry_callback: Optional[Callable[[dict], None]] = None
        self.on_control_callback: Optional[Callable[[dict], None]] = None
        self.connected = False
        self._lock = threading.Lock()

        # Instantiate Paho client supporting v2 or v1
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        except Exception:
            self.client = mqtt.Client(client_id=self.client_id)

        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set()  # HiveMQ cloud requires TLS on port 8883
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, *args):
        if rc == 0:
            self.connected = True
            print(f"[MQTT] Connected to {self.broker}:{self.port} successfully.")
            client.subscribe([(config.mqtt_topic_live, 0), (config.mqtt_topic_control, 1)])
        else:
            print(f"[MQTT] Connect failed with status code: {rc}")

    def _on_disconnect(self, client, userdata, *args, **kwargs):
        self.connected = False
        print("[MQTT] Disconnected from broker. Auto-reconnect active.")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))
            if topic == config.mqtt_topic_live and self.on_telemetry_callback:
                self.on_telemetry_callback(payload)
            elif topic == config.mqtt_topic_control and self.on_control_callback:
                self.on_control_callback(payload)
        except Exception as e:
            print(f"[MQTT] Message handling error: {e}")

    def start(self):
        def connect_loop():
            while True:
                try:
                    self.client.connect(self.broker, self.port, keepalive=60)
                    self.client.loop_start()
                    break
                except Exception as e:
                    print(f"[MQTT] Initial connect retry in 3s: {e}")
                    time.sleep(3.0)

        t = threading.Thread(target=connect_loop, daemon=True)
        t.start()

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def publish_control(self, payload: dict) -> bool:
        with self._lock:
            try:
                msg = json.dumps(payload)
                info = self.client.publish(config.mqtt_topic_control, msg, qos=1)
                return info.rc == mqtt.MQTT_ERR_SUCCESS
            except Exception as e:
                print(f"[MQTT] Error publishing control command: {e}")
                return False

    def publish_telemetry(self, payload: dict) -> bool:
        with self._lock:
            try:
                msg = json.dumps(payload)
                info = self.client.publish(config.mqtt_topic_live, msg, qos=0)
                return info.rc == mqtt.MQTT_ERR_SUCCESS
            except Exception as e:
                print(f"[MQTT] Error publishing telemetry: {e}")
                return False
