import os
import time
import json
import asyncio
import datetime
import threading
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import paho.mqtt.client as mqtt
import uvicorn

import sys

# Ensure src/ and project root are in sys.path
CURRENT_FILE = os.path.abspath(__file__)
SRC_DIR = os.path.dirname(os.path.dirname(CURRENT_FILE))
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
    from services import grid_analytics
except ImportError:
    from src.core.config import config
    from src.core.database import db
    from src.services.ml_engine import ml_engine
    from src.services.safety_engine import safety_engine
    from src.services.telegram_service import telegram
    from src.services import grid_analytics

app = FastAPI(title="Industrial Smart Grid SCADA & Digital Twin")

# Global Shared State
latest_telemetry: Dict[str, Any] = {
    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "esp32_online": False,
    "hardware_status": "OFFLINE",
    "last_seen_sec": None,
    "mode": "DUAL SMPS",
    "current_limit": 5000.0,
    "total_current": 0.0,
    "total_power": 0.0,
    "predicted_current": 0.0,
    "predicted_power": 0.0,
    "warning_level": 0,
    "warning_message": "ESP32 HARDWARE OFFLINE — AWAITING SENSOR TELEMETRY",
    "control_mode": "AUTO",
    "fault_detected": 0,
    "fault_load": "NONE",
    "fault_type": "NORMAL",
    "severity": "NONE",
    "sources": {"smps1": False, "smps2": False, "battery": False},
    "hospital": {"relay": 1, "current": 0.0, "power": 0.0, "status": "OFFLINE"},
    "street": {"relay": 1, "current": 0.0, "power": 0.0, "status": "OFFLINE"},
    "house": {"relay": 1, "current": 0.0, "power": 0.0, "status": "OFFLINE"},
    "industry": {"relay": 1, "current": 0.0, "power": 0.0, "status": "OFFLINE"},
    "critical": {"relay": 1, "current": 0.0, "power": 0.0, "status": "OFFLINE"},
    "recent_actions": [],
    "events": []
}

telemetry_history: List[Dict[str, Any]] = []
MAX_HISTORY = 60
last_mqtt_time: float = 0.0
is_initialized: bool = False

NOMINAL_CURRENTS = {
    "hospital": 252.0,
    "street": 391.0,
    "house": 238.0,
    "industry": 236.0,
    "critical": 298.5
}

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Background MQTT Client for Dashboard
mqtt_client: Optional[mqtt.Client] = None

def on_mqtt_connect(client, userdata, flags, rc, *args):
    print("[Dashboard MQTT] Connected to HiveMQ broker successfully!")
    client.subscribe([(config.mqtt_topic_live, 0), (config.mqtt_topic_control, 0)])

def on_mqtt_message(client, userdata, msg):
    global latest_telemetry, telemetry_history, last_mqtt_time
    last_mqtt_time = time.time()
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode("utf-8"))

        if topic == config.mqtt_topic_live:
            data = payload.get("data", payload)
            if not isinstance(data, dict):
                return

            flat = ml_engine.flatten_raw_telemetry(data)
            pred_row = ml_engine.run_inference_and_diagnostics(
                flat,
                commanded_relays=safety_engine.commanded_relays,
                tripped_relays=safety_engine.tripped_relays,
                stuck_relays=safety_engine.stuck_relays
            )

            ts = pred_row["timestamp"]
            limit = float(pred_row["current_limit"])
            tot_i = float(pred_row["total_current"])
            tot_p = float(pred_row["total_power"])
            util = (tot_i / limit * 100.0) if limit > 0 else 0.0

            warn_lvl = int(pred_row.get("warning_level", 0))
            warn_msg = str(pred_row.get("warning_message", "NORMAL"))

            latest_telemetry.update({
                "timestamp": ts,
                "esp32_online": True,
                "hardware_status": "ONLINE (LIVE HARDWARE)",
                "last_seen_sec": 0.0,
                "mode": pred_row["mode"],
                "current_limit": limit,
                "total_current": tot_i,
                "total_power": round(tot_p / 1000.0, 2) if tot_p > 100 else round(tot_p, 2),
                "predicted_current": float(pred_row["predicted_current"]),
                "predicted_power": float(pred_row["predicted_power"]),
                "utilization": round(util, 1),
                "warning_level": warn_lvl,
                "warning_message": warn_msg,
                "control_mode": safety_engine.control_mode,
                "fault_detected": pred_row["fault_detected"],
                "fault_load": pred_row["fault_load"],
                "fault_type": pred_row["fault_type"],
                "severity": pred_row["severity"],
                "loads_on_count": pred_row["loads_on_count"],
                "healthy_loads_count": pred_row["healthy_loads_count"],
                "prediction_breakdown": pred_row["prediction_breakdown"],
                "sources": {
                    "smps1": bool(pred_row.get("smps1", True)),
                    "smps2": bool(pred_row.get("smps2", True)),
                    "battery": bool(pred_row.get("battery", False))
                }
            })

            # Branch loads
            for l in ["hospital", "street", "house", "industry"]:
                c_val = float(pred_row.get(f"{l}_current", 0.0))
                r_val = int(pred_row.get(f"{l}_relay", 1))
                diag_val = pred_row.get("branch_diagnostics", {}).get(l, "NORMAL")
                latest_telemetry[l] = {
                    "relay": r_val,
                    "current": c_val,
                    "power": round(c_val * 12.0 / 1000.0, 2),
                    "status": diag_val
                }

            crit_c = float(pred_row.get("critical_current", 300.0))
            latest_telemetry["critical"] = {
                "relay": 1,
                "current": crit_c,
                "power": round(crit_c * 12.0 / 1000.0, 2),
                "status": pred_row.get("branch_diagnostics", {}).get("critical", "NORMAL")
            }

            latest_telemetry["recent_actions"] = safety_engine.recent_actions

            # Append to rolling history
            clean_time = ts[-8:] if len(ts) >= 8 else ts
            point = {
                "time": clean_time,
                "total_current": tot_i,
                "predicted_current": float(pred_row["predicted_current"]),
                "limit": limit,
                "hospital": latest_telemetry["hospital"]["current"],
                "street": latest_telemetry["street"]["current"],
                "house": latest_telemetry["house"]["current"],
                "industry": latest_telemetry["industry"]["current"],
                "critical": latest_telemetry["critical"]["current"],
            }
            telemetry_history.append(point)
            if len(telemetry_history) > MAX_HISTORY:
                telemetry_history.pop(0)

            # Broadcast to connected WebSockets
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast({"type": "telemetry", "data": latest_telemetry, "point": point}),
                        loop
                    )
            except Exception:
                pass

        elif topic == config.mqtt_topic_control:
            cmd = payload.get("cmd", "")
            if cmd == "MODE_CHANGE":
                safety_engine.control_mode = payload.get("mode", "AUTO")
                latest_telemetry["control_mode"] = safety_engine.control_mode
            elif cmd in ("MANUAL_OVERRIDE", "TRIP", "SHED", "RESTORE"):
                load = payload.get("load", "").lower()
                state = payload.get("state", None)
                if state is not None and load in latest_telemetry:
                    latest_telemetry[load]["relay"] = int(state)
                    safety_engine.commanded_relays[load] = int(state)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast({"type": "telemetry", "data": latest_telemetry}),
                        loop
                    )
            except Exception:
                pass

    except Exception as e:
        print(f"[Dashboard MQTT Error]: {e}")

def start_mqtt_client():
    global mqtt_client
    try:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"DASHBOARD_UI_{int(time.time())}")
        except Exception:
            client = mqtt.Client(client_id=f"DASHBOARD_UI_{int(time.time())}")

        client.username_pw_set(config.mqtt_user, config.mqtt_password)
        client.tls_set()
        client.on_connect = on_mqtt_connect
        client.on_message = on_mqtt_message
        client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)
        client.loop_start()
        mqtt_client = client
    except Exception as e:
        print(f"[Dashboard] MQTT connection notice: {e}")

@app.on_event("startup")
def startup_event():
    start_mqtt_client()

@app.on_event("shutdown")
def shutdown_event():
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

# WebSocket Endpoint
@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        status_data = get_status()
        history = telemetry_history if len(telemetry_history) >= 10 else db.get_recent_history(35)
        await websocket.send_json({
            "type": "init",
            "telemetry": status_data,
            "history": history
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# REST API Endpoints
@app.get("/api/history")
def get_history():
    if len(telemetry_history) >= 15:
        return telemetry_history
    return db.get_recent_history(35)

@app.get("/api/status")
def get_status():
    global latest_telemetry, is_initialized, last_mqtt_time, telemetry_history

    now = time.time()
    time_since_mqtt = (now - last_mqtt_time) if last_mqtt_time > 0 else 9999.0
    has_live_mqtt = (last_mqtt_time > 0) and (time_since_mqtt < 4.5)

    if not is_initialized:
        db_tel = db.get_latest_telemetry()
        if db_tel:
            mode = str(db_tel.get("mode", "DUAL SMPS"))
            limit = float(db_tel.get("current_limit", 5000.0))
            latest_telemetry["mode"] = mode
            latest_telemetry["current_limit"] = limit
            for l in ["hospital", "street", "house", "industry"]:
                r_val = int(db_tel.get(f"{l}_relay", 1))
                latest_telemetry[l]["relay"] = r_val
                safety_engine.commanded_relays[l] = r_val
        is_initialized = True

    latest_telemetry["esp32_online"] = has_live_mqtt
    latest_telemetry["last_seen_sec"] = round(time_since_mqtt, 1) if last_mqtt_time > 0 else None

    if not has_live_mqtt:
        # ESP32 is OFF / Disconnected.
        # DO NOT GENERATE ANY FALSE MEASUREMENTS OR RANDOM JITTER.
        latest_telemetry["hardware_status"] = "OFFLINE"
        
        # Zero out currents so no false readings appear
        for l in ["hospital", "street", "house", "industry", "critical"]:
            if l in latest_telemetry:
                latest_telemetry[l]["current"] = 0.0
                latest_telemetry[l]["power"] = 0.0
                latest_telemetry[l]["status"] = "OFFLINE"

        latest_telemetry["total_current"] = 0.0
        latest_telemetry["total_power"] = 0.0
        latest_telemetry["utilization"] = 0.0
        latest_telemetry["predicted_current"] = 0.0
        latest_telemetry["predicted_power"] = 0.0
        latest_telemetry["warning_level"] = 0
        latest_telemetry["sources"] = {"smps1": False, "smps2": False, "battery": False}

        if last_mqtt_time == 0:
            latest_telemetry["warning_message"] = f"ESP32 HARDWARE OFFLINE — Awaiting sensor telemetry on MQTT topic '{config.mqtt_topic_live}'"
        else:
            latest_telemetry["warning_message"] = f"ESP32 HARDWARE OFFLINE — Telemetry stream timed out ({latest_telemetry['last_seen_sec']}s ago). Power on ESP32 to resume live measurements."

    db_events = db.get_recent_events(20)
    latest_telemetry["events"] = db_events
    latest_telemetry["recent_actions"] = safety_engine.recent_actions
    latest_telemetry["control_mode"] = safety_engine.control_mode
    return latest_telemetry

@app.get("/api/events")
def get_events():
    return db.get_recent_events(20)

@app.post("/api/mode")
async def set_control_mode(request: Request):
    data = await request.json()
    new_mode = data.get("mode", "AUTO").upper()
    if new_mode in ["AUTO", "MANUAL"]:
        safety_engine.control_mode = new_mode
        latest_telemetry["control_mode"] = new_mode
        cmd = {
            "cmd": "MODE_CHANGE",
            "mode": new_mode,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if mqtt_client:
            mqtt_client.publish(config.mqtt_topic_control, json.dumps(cmd), qos=1)
        telegram.alert_mode_change(new_mode)
        await manager.broadcast({"type": "mode", "mode": new_mode})
        return {"success": True, "control_mode": new_mode}
    raise HTTPException(status_code=400, detail="Invalid mode")

@app.post("/api/relay/control")
async def control_relay(request: Request):
    data = await request.json()
    load = data.get("load", "").lower()
    state = int(data.get("state", 1))

    if load not in ["hospital", "street", "house", "industry"]:
        raise HTTPException(status_code=400, detail="Invalid load name")

    safety_engine.commanded_relays[load] = state
    if state == 1:
        safety_engine.relay_turn_on_time[load] = time.time()
        safety_engine.tripped_relays.discard(load)
    else:
        safety_engine.relay_turn_off_time[load] = time.time()

    if load in latest_telemetry:
        latest_telemetry[load]["relay"] = state
        if state == 0:
            latest_telemetry[load]["current"] = 0.0
            latest_telemetry[load]["power"] = 0.0
            latest_telemetry[load]["status"] = "SHED"
        else:
            c_nom = NOMINAL_CURRENTS.get(load, 240.0)
            latest_telemetry[load]["current"] = c_nom
            latest_telemetry[load]["power"] = round(c_nom * 12.0 / 1000.0, 2)
            latest_telemetry[load]["status"] = "NORMAL"

    # Immediately recalculate total grid draw, power and utilization
    tot_i = latest_telemetry.get("critical", {}).get("current", 298.5)
    for l in ["hospital", "street", "house", "industry"]:
        if latest_telemetry.get(l, {}).get("relay", 1) == 1:
            tot_i += latest_telemetry[l].get("current", 0.0)

    tot_i = round(tot_i, 1)
    limit = float(latest_telemetry.get("current_limit", 5000.0))
    util = round((tot_i / limit * 100.0) if limit > 0 else 0.0, 1)
    tot_p = round(tot_i * 12.0 / 1000.0, 2)

    latest_telemetry["total_current"] = tot_i
    latest_telemetry["total_power"] = tot_p
    latest_telemetry["utilization"] = util

    # Run ML diagnostics for immediate prediction updates
    pred_res = ml_engine.run_inference_and_diagnostics(
        latest_telemetry,
        commanded_relays={l: latest_telemetry[l]["relay"] for l in ["hospital", "street", "house", "industry"]},
        tripped_relays=safety_engine.tripped_relays,
        stuck_relays=safety_engine.stuck_relays
    )
    latest_telemetry["prediction_breakdown"] = pred_res.get("prediction_breakdown", {})
    latest_telemetry["predicted_current"] = float(pred_res.get("predicted_current", tot_i))
    latest_telemetry["predicted_power"] = round(float(pred_res.get("predicted_power", tot_p)), 2)

    cmd = {
        "cmd": "MANUAL_OVERRIDE",
        "load": load,
        "state": state,
        "reason": "Operator Manual SCADA Actuation",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if mqtt_client:
        try:
            mqtt_client.publish(config.mqtt_topic_control, json.dumps(cmd), qos=1)
        except Exception:
            pass
    telegram.alert_manual_override(load, state)

    event_text = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] MANUAL: {load.upper()} -> {'ON' if state == 1 else 'OFF'}"
    safety_engine.recent_actions.insert(0, event_text)

    await manager.broadcast({"type": "action", "event": event_text})
    await manager.broadcast({"type": "telemetry", "data": latest_telemetry})
    return {"success": True, "load": load, "state": state, "data": latest_telemetry}

@app.get("/api/analytics/summary")
def get_analytics_summary():
    df_tel, df_act = grid_analytics.load_data_from_db()
    return grid_analytics.compute_analytics(df_tel, df_act)

@app.get("/api/models/matrix")
def get_model_matrix():
    matrix_path = os.path.join(config.script_dir, "MODEL_BENCHMARK_MATRIX.json")
    if os.path.exists(matrix_path):
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

@app.get("/api/report/pdf")
def download_pdf_report():
    results = grid_analytics.run_full_analytics(generate_pdf=True, generate_csv=True)
    pdf_path = results.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf", filename="smart_grid_analytics_report.pdf")
    raise HTTPException(status_code=500, detail="Could not generate PDF report")

@app.get("/api/report/csv")
def download_csv_summary():
    results = grid_analytics.run_full_analytics(generate_pdf=False, generate_csv=True)
    csv_path = results.get("csv_path")
    if csv_path and os.path.exists(csv_path):
        return FileResponse(csv_path, media_type="text/csv", filename="smart_grid_summary.csv")
    raise HTTPException(status_code=500, detail="Could not generate CSV export")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Grid AI Control Center & Digital Twin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        grid: {
                            950: '#070b14',
                            900: '#0b0f19',
                            850: '#0f172a',
                            800: '#131d31',
                            750: '#17233c',
                            700: '#1e293b',
                            600: '#334155'
                        }
                    },
                    fontFamily: {
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                        mono: ['JetBrains Mono', 'Fira Code', 'monospace']
                    }
                }
            }
        }
    </script>
    <style>
        @keyframes flowPulse {
            0% { stroke-dashoffset: 24; }
            100% { stroke-dashoffset: 0; }
        }
        .flow-active {
            stroke-dasharray: 6, 6;
            animation: flowPulse 1.4s linear infinite;
        }
        .busbar-glow {
            filter: drop-shadow(0 0 10px rgba(14, 165, 233, 0.5));
        }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #070b14; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #334155; }
        .tab-btn.active {
            background-color: rgba(14, 165, 233, 0.1);
            color: #38bdf8;
            border-left-color: #38bdf8;
            font-weight: 700;
        }
    </style>
</head>
<body class="bg-grid-950 text-slate-100 font-sans min-h-screen flex flex-col antialiased selection:bg-cyan-600 selection:text-white">

    <!-- Top Navigation Bar -->
    <header class="bg-grid-900/95 backdrop-blur border-b border-grid-700/80 sticky top-0 z-50 px-4 lg:px-6 py-2.5">
        <div class="flex items-center justify-between gap-4">
            
            <!-- Left: Brand / Title -->
            <div class="flex items-center space-x-3">
                <button onclick="toggleSidebar()" class="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-grid-800 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
                </button>
                <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md shadow-cyan-500/20 shrink-0">
                    <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-sm font-black tracking-tight text-white uppercase">Smart Grid AI Control Center</span>
                        <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">v2.0 EDGE</span>
                    </div>
                    <p class="text-[11px] text-slate-400 font-medium hidden sm:block">Digital Twin & Autonomous Capacity Protection SCADA</p>
                </div>
            </div>

            <!-- Center/Right Status & Global Action Bar -->
            <div class="flex items-center gap-2.5">
                
                <!-- ESP32 Physical Hardware Status Badge -->
                <div id="espHwBadge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs font-mono font-bold text-rose-300 transition-all duration-300">
                    <span id="espHwDot" class="w-2 h-2 rounded-full bg-rose-500"></span>
                    <span id="espHwText">ESP32 OFFLINE</span>
                </div>

                <!-- Live Heartbeat / Countdown -->
                <div class="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-grid-800/80 border border-grid-700 text-xs font-mono text-slate-300">
                    <span id="liveStatusDot" class="w-2 h-2 rounded-full bg-slate-500"></span>
                    <span>Sync: <b id="countdownTimer" class="text-cyan-400">2s</b></span>
                    <button onclick="forceRefresh()" title="Trigger Immediate 2s Polling Synchronization" class="text-slate-400 hover:text-white transition ml-1 font-bold">
                        <svg class="w-3.5 h-3.5 hover:rotate-180 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                    </button>
                </div>

                <!-- Operating Mode Switcher -->
                <div class="bg-grid-800/90 p-1 rounded-lg border border-grid-700 flex items-center text-xs font-semibold">
                    <button id="btnAutoMode" onclick="setMode('AUTO')" class="px-2.5 py-1 rounded-md bg-blue-600 text-white transition shadow-sm font-bold flex items-center gap-1.5">
                        <span class="w-1.5 h-1.5 rounded-full bg-white"></span> AI AUTO
                    </button>
                    <button id="btnManualMode" onclick="setMode('MANUAL')" class="px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition font-medium flex items-center gap-1.5">
                        MANUAL
                    </button>
                </div>

                <!-- Report Actions -->
                <div class="flex items-center gap-1.5">
                    <a href="/api/report/pdf" target="_blank" class="px-3 py-1.5 rounded-lg bg-indigo-600/90 hover:bg-indigo-600 text-white text-xs font-bold transition shadow-sm shadow-indigo-500/20 flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
                        <span class="hidden md:inline">PDF Report</span>
                    </a>
                    <a href="/api/report/csv" target="_blank" class="px-3 py-1.5 rounded-lg bg-grid-800 hover:bg-grid-750 text-slate-300 hover:text-white border border-grid-700 text-xs font-semibold transition hidden sm:flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                        <span>CSV Export</span>
                    </a>
                </div>

            </div>
        </div>
    </header>

    <!-- Application Body Shell (Sidebar + Main Content) -->
    <div class="flex-1 flex overflow-hidden">

        <!-- Sidebar Navigation -->
        <aside id="appSidebar" class="w-64 bg-grid-900/90 border-r border-grid-700/70 flex flex-col justify-between shrink-0 transition-transform duration-300 z-40 fixed inset-y-0 left-0 pt-16 lg:pt-0 lg:static lg:translate-x-0 -translate-x-full">
            
            <!-- Navigation Links -->
            <div class="p-3 space-y-1 overflow-y-auto">
                <div class="px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">SCADA Navigation</div>
                
                <button onclick="switchTab('overview')" class="tab-btn active w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>
                    <span>Overview & KPIs</span>
                </button>

                <button onclick="switchTab('digital-twin')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>
                    <span>Digital Twin SLD</span>
                </button>

                <button onclick="switchTab('ai-forecast')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                    <span>AI Load Forecasting</span>
                </button>

                <button onclick="switchTab('faults')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                    <span>Fault Diagnostics</span>
                </button>

                <button onclick="switchTab('control')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>
                    <span>Relay Control Deck</span>
                </button>

                <button onclick="switchTab('events')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>
                    <span>Actuation Audit Trail</span>
                </button>

                <button onclick="switchTab('analytics')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                    <span>Analytics & Reliability</span>
                </button>

                <button onclick="switchTab('models')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>
                    <span>Model Benchmarks</span>
                </button>

                <button onclick="switchTab('specs')" class="tab-btn w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-grid-800/80 transition border-l-2 border-transparent">
                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                    <span>Hardware Pinouts & Viva</span>
                </button>
            </div>

            <!-- Edge System Telemetry Indicators -->
            <div class="p-3.5 m-3 rounded-xl bg-grid-950/80 border border-grid-700/80 space-y-2 text-[11px] font-mono">
                <div class="text-[10px] uppercase font-bold text-slate-400 font-sans tracking-wider border-b border-grid-800 pb-1.5 flex items-center justify-between">
                    <span>Edge Telemetry</span>
                    <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                </div>
                <div class="flex items-center justify-between text-slate-300">
                    <span class="text-slate-400 font-sans">ESP32 Firmware</span>
                    <span class="text-emerald-400 font-bold" id="edgeEsp32State">ONLINE (v2.0)</span>
                </div>
                <div class="flex items-center justify-between text-slate-300">
                    <span class="text-slate-400 font-sans">HiveMQ Broker</span>
                    <span class="text-emerald-400 font-bold">TLS 8883 OK</span>
                </div>
                <div class="flex items-center justify-between text-slate-300">
                    <span class="text-slate-400 font-sans">AI Forecaster</span>
                    <span class="text-indigo-400 font-bold">36-FEAT RDY</span>
                </div>
                <div class="flex items-center justify-between text-slate-300">
                    <span class="text-slate-400 font-sans">Database Pool</span>
                    <span class="text-cyan-400 font-bold">SQLITE WAL</span>
                </div>
            </div>
        </aside>

        <!-- Main Content Area -->
        <main class="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">

            <!-- SECTION 1: EXECUTIVE HERO STATUS BANNER -->
            <section id="section-hero">
                <div id="warningBanner" class="rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-emerald-950/30 border-emerald-800/40 text-emerald-300 shadow-lg">
                    <div class="flex items-start sm:items-center space-x-3.5">
                        <div class="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center shrink-0" id="warningIconBox">
                            <svg id="warningIcon" class="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        </div>
                        <div>
                            <div class="flex items-center gap-2 flex-wrap">
                                <span id="warningTitle" class="font-extrabold text-sm sm:text-base tracking-wide uppercase text-white">SYSTEM HEALTHY — NOMINAL OPERATION</span>
                                <span id="headerModeBadge" class="text-[10px] font-mono font-extrabold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">DUAL SMPS</span>
                            </div>
                            <div id="warningDetail" class="text-xs text-slate-300 mt-0.5 leading-relaxed">
                                Physical grid operating within 2-SD limits. 15s anti-chattering dwell & priority packing armed.
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center md:flex-col md:items-end justify-between border-t md:border-t-0 border-grid-800 pt-2 md:pt-0 shrink-0 text-right">
                        <div class="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Active Capacity Ceiling</div>
                        <div id="gridLimitText" class="text-xl sm:text-2xl font-black text-slate-100 font-mono">5000 mA</div>
                    </div>
                </div>
            </section>

            <!-- SECTION 2: 4 PRIMARY KPI CARDS -->
            <section id="section-kpis" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                
                <!-- KPI 1: Total Current -->
                <div class="bg-grid-900/90 border border-grid-700/80 p-4 sm:p-5 rounded-xl shadow-md hover:border-cyan-500/50 transition duration-300">
                    <div class="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
                        <span class="tracking-wide">TOTAL CURRENT</span>
                        <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                    </div>
                    <div class="flex items-baseline gap-1.5 my-1">
                        <span id="totCurrentVal" class="text-2xl sm:text-3xl font-black text-white font-mono">0.0</span>
                        <span class="text-xs font-bold text-slate-400">mA</span>
                    </div>
                    <div class="text-[11px] text-cyan-400 font-mono truncate" id="subPredCurrentText">🔮 AI Pred: 0.0 mA</div>
                </div>

                <!-- KPI 2: Active Power -->
                <div class="bg-grid-900/90 border border-grid-700/80 p-4 sm:p-5 rounded-xl shadow-md hover:border-amber-500/50 transition duration-300">
                    <div class="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
                        <span class="tracking-wide">ACTIVE POWER</span>
                        <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                    </div>
                    <div class="flex items-baseline gap-1.5 my-1">
                        <span id="totPowerVal" class="text-2xl sm:text-3xl font-black text-white font-mono">0.00</span>
                        <span class="text-xs font-bold text-slate-400">W</span>
                    </div>
                    <div class="text-[11px] text-amber-400 font-mono truncate" id="predictedPowerText">🔮 AI Pred: 0.00 W</div>
                </div>

                <!-- KPI 3: Grid Utilization -->
                <div class="bg-grid-900/90 border border-grid-700/80 p-4 sm:p-5 rounded-xl shadow-md hover:border-emerald-500/50 transition duration-300">
                    <div class="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
                        <span class="tracking-wide">UTILIZATION</span>
                        <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                    </div>
                    <div class="flex items-baseline gap-1.5 my-1">
                        <span id="utilPctVal" class="text-2xl sm:text-3xl font-black text-white font-mono">0.0</span>
                        <span class="text-xs font-bold text-slate-400">%</span>
                    </div>
                    <!-- Custom Visual Capacity Bar -->
                    <div class="w-full bg-grid-800 rounded-full h-2 my-1 overflow-hidden border border-grid-700">
                        <div id="utilCapacityBar" class="bg-emerald-500 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                    <div class="text-[10px] text-slate-400 font-mono flex justify-between mt-1">
                        <span id="headroomText">Headroom: 100%</span>
                        <span>Trip: 85%</span>
                    </div>
                </div>

                <!-- KPI 4: System Status -->
                <div class="bg-grid-900/90 border border-grid-700/80 p-4 sm:p-5 rounded-xl shadow-md hover:border-purple-500/50 transition duration-300">
                    <div class="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
                        <span class="tracking-wide">CIRCUIT INTEGRITY</span>
                        <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                    </div>
                    <div class="flex items-baseline gap-1.5 my-1">
                        <span id="systemHealthStatus" class="text-xl sm:text-2xl font-black text-emerald-400 font-mono">HEALTHY</span>
                    </div>
                    <div class="text-[11px] text-slate-400 font-mono truncate" id="systemHealthDesc">4/4 Loads Online • 0 Faults</div>
                </div>
            </section>

            <!-- SECTION 3: POWER SOURCES SECTION (3 Dedicated Cards) -->
            <section id="section-sources">
                <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-2">
                    <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                    <span>Power Generation Sources</span>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    
                    <!-- SMPS 1 -->
                    <div id="cardSmps1" class="bg-grid-900/90 border border-cyan-500/40 rounded-xl p-4 flex items-center justify-between shadow-sm">
                        <div class="flex items-center space-x-3">
                            <div class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" id="dotSmps1"></div>
                            <div>
                                <h4 class="text-sm font-bold text-white">SMPS 1 (Grid Main)</h4>
                                <p class="text-[11px] text-slate-400 font-mono">12.0V DC • 2500 mA Max</p>
                            </div>
                        </div>
                        <span id="badgeSmps1" class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">ONLINE</span>
                    </div>

                    <!-- SMPS 2 -->
                    <div id="cardSmps2" class="bg-grid-900/90 border border-cyan-500/40 rounded-xl p-4 flex items-center justify-between shadow-sm">
                        <div class="flex items-center space-x-3">
                            <div class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" id="dotSmps2"></div>
                            <div>
                                <h4 class="text-sm font-bold text-white">SMPS 2 (Grid Aux)</h4>
                                <p class="text-[11px] text-slate-400 font-mono">12.0V DC • 2500 mA Max</p>
                            </div>
                        </div>
                        <span id="badgeSmps2" class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">ONLINE</span>
                    </div>

                    <!-- Battery Backup -->
                    <div id="cardBattery" class="bg-grid-900/90 border border-grid-700 rounded-xl p-4 flex items-center justify-between shadow-sm">
                        <div class="flex items-center space-x-3">
                            <div class="w-3 h-3 rounded-full bg-slate-500" id="dotBattery"></div>
                            <div>
                                <h4 class="text-sm font-bold text-slate-300">Battery Storage</h4>
                                <p class="text-[11px] text-slate-500 font-mono">12.0V DC • 800 mA Standby</p>
                            </div>
                        </div>
                        <span id="badgeBattery" class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">STANDBY</span>
                    </div>

                </div>
            </section>

            <!-- SECTION 4: DIGITAL TWIN SINGLE-LINE DIAGRAM (SLD) -->
            <section id="section-sld" class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-5 shadow-xl relative overflow-hidden">
                <div class="flex items-center justify-between border-b border-grid-800 pb-3 mb-4">
                    <div class="flex items-center gap-2.5">
                        <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/></svg>
                        <h3 class="font-extrabold text-sm text-white tracking-wider uppercase">Interactive Digital Twin Single-Line Diagram (SLD)</h3>
                    </div>
                    <div class="flex items-center gap-4 text-xs font-mono text-slate-400 hidden sm:flex">
                        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block"></span> Breaker Closed</span>
                        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"></span> Breaker Open/Shed</span>
                    </div>
                </div>

                <!-- SVG Diagram Canvas -->
                <div class="w-full overflow-x-auto">
                    <svg id="digitalTwinSvg" viewBox="0 0 1000 240" class="w-full min-w-[760px] h-auto select-none">
                        <defs>
                            <linearGradient id="busGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" stop-color="#0284c7"/>
                                <stop offset="100%" stop-color="#38bdf8"/>
                            </linearGradient>
                        </defs>

                        <!-- Sources (Left) -->
                        <g transform="translate(30, 25)">
                            <rect width="115" height="42" rx="6" fill="#0b1120" stroke="#0ea5e9" stroke-width="1.5"/>
                            <circle cx="15" cy="21" r="5" id="ledSmps1" fill="#10b981"/>
                            <text x="28" y="18" fill="#f1f5f9" font-size="11" font-weight="bold">SMPS 1 (Grid)</text>
                            <text x="28" y="32" fill="#94a3b8" font-size="9" font-family="monospace">12V / 2500mA</text>
                        </g>

                        <g transform="translate(30, 85)">
                            <rect width="115" height="42" rx="6" fill="#0b1120" stroke="#0ea5e9" stroke-width="1.5"/>
                            <circle cx="15" cy="21" r="5" id="ledSmps2" fill="#10b981"/>
                            <text x="28" y="18" fill="#f1f5f9" font-size="11" font-weight="bold">SMPS 2 (Grid)</text>
                            <text x="28" y="32" fill="#94a3b8" font-size="9" font-family="monospace">12V / 2500mA</text>
                        </g>

                        <g transform="translate(30, 145)">
                            <rect width="115" height="42" rx="6" fill="#0b1120" stroke="#475569" stroke-width="1.5"/>
                            <circle cx="15" cy="21" r="5" id="ledBattery" fill="#64748b"/>
                            <text x="28" y="18" fill="#cbd5e1" font-size="11" font-weight="bold">Battery Storage</text>
                            <text x="28" y="32" fill="#64748b" font-size="9" font-family="monospace">12V / 800mA</text>
                        </g>

                        <!-- Feeder Paths to Busbar -->
                        <path d="M 145 46 L 220 110" stroke="#0ea5e9" stroke-width="2" class="flow-active" id="pathSmps1"/>
                        <path d="M 145 106 L 220 110" stroke="#0ea5e9" stroke-width="2" class="flow-active" id="pathSmps2"/>
                        <path d="M 145 166 L 220 110" stroke="#475569" stroke-width="1.5" id="pathBattery"/>

                        <!-- Central 12V DC Busbar -->
                        <rect x="220" y="20" width="14" height="195" rx="4" fill="url(#busGrad)" class="busbar-glow"/>
                        <text x="238" y="15" fill="#38bdf8" font-size="10" font-weight="bold" font-family="monospace">12V DC BUSBAR</text>

                        <!-- Branch 1: Critical Load (Permanent Bus Connection, Non-Shed) -->
                        <g transform="translate(234, 25)">
                            <path d="M 0 10 L 90 10" stroke="#10b981" stroke-width="2.5" class="flow-active"/>
                            <rect x="90" y="-8" width="135" height="38" rx="6" fill="#064e3b" stroke="#10b981" stroke-width="1.5"/>
                            <text x="100" y="10" fill="#a7f3d0" font-size="11" font-weight="bold">Critical (I2C2 0x40)</text>
                            <text x="100" y="23" fill="#6ee7b7" font-size="9" font-family="monospace" id="dtCritCurr">300.0 mA • PROTECTED</text>
                        </g>

                        <!-- Branch 2: Hospital (GPIO14, Priority 4) -->
                        <g transform="translate(234, 68)">
                            <path d="M 0 10 L 40 10" stroke="#0ea5e9" stroke-width="2" id="dtLineHosp" class="flow-active"/>
                            <circle cx="45" cy="10" r="4" fill="#0ea5e9"/>
                            <line x1="45" y1="10" x2="65" y2="10" stroke="#10b981" stroke-width="3" id="dtSwHosp"/>
                            <circle cx="65" cy="10" r="4" fill="#0ea5e9"/>
                            <path d="M 65 10 L 90 10" stroke="#0ea5e9" stroke-width="2"/>
                            <rect x="90" y="-8" width="135" height="38" rx="6" fill="#0b1120" stroke="#0284c7" stroke-width="1.5" id="dtBoxHosp"/>
                            <text x="100" y="10" fill="#f1f5f9" font-size="11" font-weight="bold">Hospital (P4)</text>
                            <text x="100" y="23" fill="#93c5fd" font-size="9" font-family="monospace" id="dtHospCurr">250.0 mA • GPIO14</text>
                        </g>

                        <!-- Branch 3: Street Lights (GPIO13, Priority 3) -->
                        <g transform="translate(234, 110)">
                            <path d="M 0 10 L 40 10" stroke="#0ea5e9" stroke-width="2" id="dtLineStrt" class="flow-active"/>
                            <circle cx="45" cy="10" r="4" fill="#0ea5e9"/>
                            <line x1="45" y1="10" x2="65" y2="10" stroke="#10b981" stroke-width="3" id="dtSwStrt"/>
                            <circle cx="65" cy="10" r="4" fill="#0ea5e9"/>
                            <path d="M 65 10 L 90 10" stroke="#0ea5e9" stroke-width="2"/>
                            <rect x="90" y="-8" width="135" height="38" rx="6" fill="#0b1120" stroke="#059669" stroke-width="1.5" id="dtBoxStrt"/>
                            <text x="100" y="10" fill="#f1f5f9" font-size="11" font-weight="bold">Street Lights (P3)</text>
                            <text x="100" y="23" fill="#6ee7b7" font-size="9" font-family="monospace" id="dtStrtCurr">390.0 mA • GPIO13</text>
                        </g>

                        <!-- Branch 4: House (GPIO4, Priority 2) -->
                        <g transform="translate(234, 152)">
                            <path d="M 0 10 L 40 10" stroke="#0ea5e9" stroke-width="2" id="dtLineHous" class="flow-active"/>
                            <circle cx="45" cy="10" r="4" fill="#0ea5e9"/>
                            <line x1="45" y1="10" x2="65" y2="10" stroke="#10b981" stroke-width="3" id="dtSwHous"/>
                            <circle cx="65" cy="10" r="4" fill="#0ea5e9"/>
                            <path d="M 65 10 L 90 10" stroke="#0ea5e9" stroke-width="2"/>
                            <rect x="90" y="-8" width="135" height="38" rx="6" fill="#0b1120" stroke="#d97706" stroke-width="1.5" id="dtBoxHous"/>
                            <text x="100" y="10" fill="#f1f5f9" font-size="11" font-weight="bold">Residential (P2)</text>
                            <text x="100" y="23" fill="#fcd34d" font-size="9" font-family="monospace" id="dtHousCurr">240.0 mA • GPIO4</text>
                        </g>

                        <!-- Branch 5: Industry (GPIO26, Priority 1 - First Shed) -->
                        <g transform="translate(234, 194)">
                            <path d="M 0 10 L 40 10" stroke="#0ea5e9" stroke-width="2" id="dtLineIndu" class="flow-active"/>
                            <circle cx="45" cy="10" r="4" fill="#0ea5e9"/>
                            <line x1="45" y1="10" x2="65" y2="10" stroke="#10b981" stroke-width="3" id="dtSwIndu"/>
                            <circle cx="65" cy="10" r="4" fill="#0ea5e9"/>
                            <path d="M 65 10 L 90 10" stroke="#0ea5e9" stroke-width="2"/>
                            <rect x="90" y="-8" width="135" height="38" rx="6" fill="#0b1120" stroke="#dc2626" stroke-width="1.5" id="dtBoxIndu"/>
                            <text x="100" y="10" fill="#f1f5f9" font-size="11" font-weight="bold">Industry (P1 Shed 1st)</text>
                            <text x="100" y="23" fill="#fda4af" font-size="9" font-family="monospace" id="dtInduCurr">240.0 mA • GPIO26</text>
                        </g>

                        <!-- Summary Table Block (Right) -->
                        <g transform="translate(530, 25)">
                            <rect width="215" height="190" rx="8" fill="#070b14" stroke="#1e293b" stroke-width="1.5"/>
                            <text x="16" y="25" fill="#94a3b8" font-size="11" font-weight="bold" font-family="sans-serif">DIGITAL TWIN METRICS</text>
                            <line x1="16" y1="35" x2="200" y2="35" stroke="#1e293b" stroke-width="1"/>
                            <text x="16" y="58" fill="#94a3b8" font-size="11">Total Grid Draw:</text>
                            <text x="200" y="58" text-anchor="end" fill="#38bdf8" font-size="12" font-weight="bold" font-family="monospace" id="dtSummaryTotal">1420 mA</text>
                            <text x="16" y="86" fill="#94a3b8" font-size="11">Current Limit:</text>
                            <text x="200" y="86" text-anchor="end" fill="#f1f5f9" font-size="12" font-weight="bold" font-family="monospace" id="dtSummaryLimit">5000 mA</text>
                            <text x="16" y="114" fill="#94a3b8" font-size="11">Grid Utilization:</text>
                            <text x="200" y="114" text-anchor="end" fill="#10b981" font-size="12" font-weight="bold" font-family="monospace" id="dtSummaryUtil">28.4%</text>
                            <text x="16" y="142" fill="#94a3b8" font-size="11">Restoration Headroom:</text>
                            <text x="200" y="142" text-anchor="end" fill="#a7f3d0" font-size="12" font-weight="bold" font-family="monospace" id="dtSummaryHeadroom">2780 mA</text>
                            <text x="16" y="170" fill="#94a3b8" font-size="11">Online Breakers:</text>
                            <text x="200" y="170" text-anchor="end" fill="#f1f5f9" font-size="12" font-weight="bold" font-family="monospace" id="dtSummaryBreakers">4 / 4 Active</text>
                        </g>
                    </svg>
                </div>
            </section>

            <!-- SECTION 5: LOAD STATUS DECK (Critical + 4 Controllable Branches) -->
            <section id="section-loads">
                <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        <span>Branch Load Distribution & Breaker Deck</span>
                    </div>
                    <span class="text-[10px] text-slate-500 font-mono">Priority: P4 (High) &rarr; P1 (Shed First)</span>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                    
                    <!-- 1. Critical Load (Permanent Protection) -->
                    <div class="bg-gradient-to-b from-emerald-950/40 to-grid-900 border border-emerald-600/50 rounded-xl p-4 flex flex-col justify-between shadow-md relative overflow-hidden">
                        <div class="absolute top-0 right-0 bg-emerald-500/20 text-emerald-400 text-[9px] font-mono font-bold px-2 py-0.5 rounded-bl">ALWAYS ON</div>
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <h4 class="text-sm font-extrabold text-white">Critical Load</h4>
                            </div>
                            <p class="text-[10px] text-emerald-400 font-semibold mb-2">Hospital ICU & Traffic Signal</p>
                            <div class="my-2 space-y-1">
                                <div class="text-xl font-black text-white font-mono" id="critCurrVal">300.0 mA</div>
                                <div class="text-[11px] text-slate-400 font-mono" id="critPowerVal">3.60 W (12.0V)</div>
                            </div>
                        </div>
                        <div class="mt-3 pt-2 border-t border-emerald-900/50 flex items-center justify-between text-[11px]">
                            <span class="text-emerald-300 font-bold">NON-SHEDDABLE</span>
                            <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                        </div>
                    </div>

                    <!-- 2. Hospital (P4) -->
                    <div class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-4 flex flex-col justify-between shadow-md hover:border-blue-500/50 transition duration-200">
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <h4 class="text-sm font-bold text-white">Hospital</h4>
                                <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300">P4</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] text-slate-400 mb-2">
                                <span>Relay GPIO14</span>
                                <span id="hospStatusBadge" class="text-emerald-400 font-bold">NORMAL</span>
                            </div>
                            <div class="my-2 space-y-0.5">
                                <div class="text-xl font-black text-white font-mono" id="hospCurr">0.0 mA</div>
                                <div class="text-[11px] text-slate-400 font-mono" id="hospPower">0.00 W</div>
                            </div>
                        </div>
                        <button id="btnRelayHosp" onclick="promptRelayToggle('hospital')" class="mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-sm">
                            ON (Active)
                        </button>
                    </div>

                    <!-- 3. Street Light (P3) -->
                    <div class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-4 flex flex-col justify-between shadow-md hover:border-emerald-500/50 transition duration-200">
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <h4 class="text-sm font-bold text-white">Street Light</h4>
                                <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">P3</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] text-slate-400 mb-2">
                                <span>Relay GPIO13</span>
                                <span id="strtStatusBadge" class="text-emerald-400 font-bold">NORMAL</span>
                            </div>
                            <div class="my-2 space-y-0.5">
                                <div class="text-xl font-black text-white font-mono" id="strtCurr">0.0 mA</div>
                                <div class="text-[11px] text-slate-400 font-mono" id="strtPower">0.00 W</div>
                            </div>
                        </div>
                        <button id="btnRelayStrt" onclick="promptRelayToggle('street')" class="mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-sm">
                            ON (Active)
                        </button>
                    </div>

                    <!-- 4. House (P2) -->
                    <div class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-4 flex flex-col justify-between shadow-md hover:border-amber-500/50 transition duration-200">
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <h4 class="text-sm font-bold text-white">Residential</h4>
                                <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">P2</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] text-slate-400 mb-2">
                                <span>Relay GPIO4</span>
                                <span id="housStatusBadge" class="text-emerald-400 font-bold">NORMAL</span>
                            </div>
                            <div class="my-2 space-y-0.5">
                                <div class="text-xl font-black text-white font-mono" id="housCurr">0.0 mA</div>
                                <div class="text-[11px] text-slate-400 font-mono" id="housPower">0.00 W</div>
                            </div>
                        </div>
                        <button id="btnRelayHous" onclick="promptRelayToggle('house')" class="mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-sm">
                            ON (Active)
                        </button>
                    </div>

                    <!-- 5. Industry (P1 - First Shed) -->
                    <div class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-4 flex flex-col justify-between shadow-md hover:border-rose-500/50 transition duration-200">
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <h4 class="text-sm font-bold text-white">Industry</h4>
                                <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300">P1 (Shed 1st)</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] text-slate-400 mb-2">
                                <span>Relay GPIO26</span>
                                <span id="induStatusBadge" class="text-emerald-400 font-bold">NORMAL</span>
                            </div>
                            <div class="my-2 space-y-0.5">
                                <div class="text-xl font-black text-white font-mono" id="induCurr">0.0 mA</div>
                                <div class="text-[11px] text-slate-400 font-mono" id="induPower">0.00 W</div>
                            </div>
                        </div>
                        <button id="btnRelayIndu" onclick="promptRelayToggle('industry')" class="mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-sm">
                            ON (Active)
                        </button>
                    </div>

                </div>
            </section>

            <!-- SECTION 6: AI CAPACITY FORECAST & LOAD-AWARE BREAKDOWN -->
            <section id="section-ai" class="grid grid-cols-1 lg:grid-cols-12 gap-5">
                
                <!-- AI Forecast Breakdown (8 cols) -->
                <div class="lg:col-span-8 bg-gradient-to-r from-grid-900 via-indigo-950/20 to-grid-900 border border-indigo-500/40 rounded-xl p-5 shadow-xl">
                    <div class="flex items-center justify-between border-b border-grid-800 pb-3 mb-3">
                        <div>
                            <h3 class="font-extrabold text-sm text-white tracking-wide flex items-center gap-2">
                                <span class="text-indigo-400">🔮</span> AI LOAD FORECAST & CAPACITY PREDICTION
                            </h3>
                            <p class="text-[11px] text-slate-400 mt-0.5">Machine-learning dynamic synthesis across 36 temporal and rolling demand features.</p>
                        </div>
                        <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">RF MODEL 1A</span>
                    </div>

                    <!-- 4 Compact Prediction Cards with Arrows -->
                    <div id="predBranchBreakdown" class="grid grid-cols-2 sm:grid-cols-5 gap-2.5 mb-3">
                        <!-- Populated dynamically via JS -->
                    </div>

                    <div class="p-3 rounded-lg bg-grid-950/90 border border-grid-800 text-xs text-slate-300 flex items-start gap-2.5">
                        <span class="text-indigo-400 font-bold shrink-0">MODEL SUMMARY:</span>
                        <span id="predNarrativeText" class="leading-relaxed text-slate-300">AI Forecasting active: Evaluating branch status and historical rolling windows...</span>
                    </div>
                </div>

                <!-- Causal Decision Explanation (4 cols) -->
                <div class="lg:col-span-4 bg-grid-900/90 border border-grid-700/80 rounded-xl p-5 shadow-xl flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between border-b border-grid-800 pb-2 mb-3">
                            <h4 class="font-bold text-xs uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                                <span class="text-cyan-400">🧠</span> WHY DID THE SYSTEM ACT?
                            </h4>
                            <span class="text-[10px] font-mono text-cyan-400">15s DWELL</span>
                        </div>
                        <div id="decisionExplanationList" class="space-y-2 text-xs font-mono max-h-40 overflow-y-auto">
                            <div class="text-slate-400 p-2 rounded bg-grid-950 border border-grid-800/80">
                                Grid initialized. Priority Packing armed (&le; 84% restoration ceiling).
                            </div>
                        </div>
                    </div>
                </div>

            </section>

            <!-- SECTION 7: LIVE MULTI-BRANCH TREND CHART -->
            <section id="section-chart" class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-5 shadow-md">
                <div class="flex items-center justify-between mb-3 border-b border-grid-800 pb-2.5">
                    <div>
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">Continuous 60s Multi-Branch Current Waveform</h3>
                        <p class="text-[11px] text-slate-400">Real-time comparison of Actual Total Current vs. Machine-Learning Predicted Demand</p>
                    </div>
                    <span class="text-[10px] text-cyan-400 font-mono bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/30">2.0s Telemetry Window</span>
                </div>
                <div class="h-64 sm:h-72 w-full">
                    <canvas id="liveChart"></canvas>
                </div>
            </section>

            <!-- SECTION 8: DISCRETE ACTUATION AUDIT TRAIL (SQLite) -->
            <section id="section-events" class="bg-grid-900/90 border border-grid-700/80 rounded-xl p-5 shadow-md">
                <div class="flex items-center justify-between mb-3 border-b border-grid-800 pb-2.5">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">Discrete Actuation Audit Trail (SQLite Logs)</h3>
                    </div>
                    <span class="text-[10px] text-slate-400 font-mono">Immutable Forensic Log</span>
                </div>
                <div class="overflow-x-auto max-h-52">
                    <table class="w-full text-left text-xs text-slate-300">
                        <thead class="bg-grid-950 text-slate-400 uppercase font-mono text-[10px] sticky top-0 border-b border-grid-800">
                            <tr>
                                <th class="p-2.5">Time</th>
                                <th class="p-2.5">Action</th>
                                <th class="p-2.5">Branch</th>
                                <th class="p-2.5">Reason</th>
                                <th class="p-2.5">Current</th>
                                <th class="p-2.5">Limit</th>
                                <th class="p-2.5">Context</th>
                            </tr>
                        </thead>
                        <tbody id="eventsTableBody" class="divide-y divide-grid-800/80 font-mono text-[11px]">
                            <!-- Populated dynamically via JS -->
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- SECTION 9: TECHNICAL VIVA & HARDWARE DETAILS (Collapsible Drawer) -->
            <section id="section-specs" class="bg-grid-900/80 border border-grid-700/70 rounded-xl p-4 shadow-md">
                <button onclick="toggleTechnicalDrawer()" class="w-full flex items-center justify-between text-left">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                        <span class="text-xs font-bold uppercase tracking-wider text-slate-300">Technical Hardware Specifications & Viva Documentation</span>
                    </div>
                    <span id="techDrawerArrow" class="text-slate-400 text-xs font-mono">&darr; Expand</span>
                </button>
                
                <div id="technicalDrawerContent" class="hidden mt-4 pt-4 border-t border-grid-800 space-y-4 text-xs font-mono text-slate-300">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="p-3 bg-grid-950 rounded-lg border border-grid-800">
                            <div class="text-[10px] text-cyan-400 font-bold uppercase mb-1">Dual I2C Bus Mapping</div>
                            <div>&bull; Bus 1 (Wire): GPIO27 (SDA) / GPIO33 (SCL) &rarr; INA219 0x40, 0x41, 0x44, 0x45</div>
                            <div>&bull; Bus 2 (I2C2): GPIO25 (SDA) / GPIO32 (SCL) &rarr; Critical INA219 0x40</div>
                        </div>
                        <div class="p-3 bg-grid-950 rounded-lg border border-grid-800">
                            <div class="text-[10px] text-amber-400 font-bold uppercase mb-1">Active-LOW Relay Pins</div>
                            <div>&bull; Hospital: GPIO14 (Priority 4)</div>
                            <div>&bull; Street Lights: GPIO13 (Priority 3)</div>
                            <div>&bull; Residential: GPIO4 (Priority 2)</div>
                            <div>&bull; Industry: GPIO26 (Priority 1)</div>
                        </div>
                        <div class="p-3 bg-grid-950 rounded-lg border border-grid-800">
                            <div class="text-[10px] text-purple-400 font-bold uppercase mb-1">Power Sense & Communications</div>
                            <div>&bull; SMPS1 Sense: GPIO34 (ADC1)</div>
                            <div>&bull; SMPS2 Sense: GPIO35 (ADC1)</div>
                            <div>&bull; Battery Sense: GPIO39 (ADC1)</div>
                            <div>&bull; MQTT Topic: <code>smartgrid/live</code>, <code>smartgrid/control</code></div>
                        </div>
                    </div>
                </div>
            </section>

        </main>
    </div>

    <!-- TWO-STEP MANUAL OVERRIDE CONFIRMATION MODAL -->
    <div id="confirmModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-grid-900 border border-grid-700 rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-3">
            <div class="flex items-center gap-2.5 text-amber-400 font-bold text-sm">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                <span>Confirm Manual Actuation</span>
            </div>
            <p id="confirmModalText" class="text-xs text-slate-300 leading-relaxed">
                Confirm switching relay state?
            </p>
            <div class="text-[10px] text-slate-400 bg-grid-950 p-2.5 rounded border border-grid-800 font-mono">
                Notice: Manual commands bypass the autonomous safety controller until switched back to AUTO.
            </div>
            <div class="flex justify-end gap-2 pt-2">
                <button onclick="closeConfirmModal()" class="px-3.5 py-1.5 rounded-lg bg-grid-800 text-slate-300 text-xs font-semibold hover:bg-grid-750 transition">Cancel</button>
                <button id="btnConfirmActuation" onclick="executeRelayToggle()" class="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-sm">Confirm Switch</button>
            </div>
        </div>
    </div>

    <!-- CLIENT JAVASCRIPT LOGIC -->
    <script>
        let currentMode = "AUTO";
        let pendingLoad = null;
        let pendingState = null;
        let ws = null;
        let chart = null;
        let lastSyncTimestamp = Date.now();
        let isFetching = false;

        // Tab Navigation
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            const clickedBtn = event ? event.currentTarget : null;
            if (clickedBtn) clickedBtn.classList.add('active');

            const sectionMap = {
                'overview': 'section-hero',
                'digital-twin': 'section-sld',
                'ai-forecast': 'section-ai',
                'faults': 'section-ai',
                'control': 'section-loads',
                'events': 'section-events',
                'analytics': 'section-chart',
                'models': 'section-ai',
                'specs': 'section-specs'
            };

            const targetSection = document.getElementById(sectionMap[tabId] || 'section-hero');
            if (targetSection) {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            if (window.innerWidth < 1024) toggleSidebar();
        }

        function toggleSidebar() {
            const sidebar = document.getElementById('appSidebar');
            sidebar.classList.toggle('-translate-x-full');
        }

        function toggleTechnicalDrawer() {
            const drawer = document.getElementById('technicalDrawerContent');
            const arrow = document.getElementById('techDrawerArrow');
            if (drawer.classList.contains('hidden')) {
                drawer.classList.remove('hidden');
                arrow.innerHTML = '&uarr; Collapse';
            } else {
                drawer.classList.add('hidden');
                arrow.innerHTML = '&darr; Expand';
            }
        }

        // Initialize Chart.js
        function initChart() {
            const ctx = document.getElementById('liveChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'Total Current (mA)', data: [], borderColor: '#0ea5e9', backgroundColor: 'rgba(14, 165, 233, 0.05)', borderWidth: 2.5, tension: 0.2, fill: true },
                        { label: 'AI Predicted (mA)', data: [], borderColor: '#818cf8', borderDash: [4, 4], borderWidth: 1.8, tension: 0.2, fill: false },
                        { label: 'Hospital', data: [], borderColor: '#3b82f6', borderWidth: 1.5, hidden: true },
                        { label: 'Street Lights', data: [], borderColor: '#10b981', borderWidth: 1.5, hidden: true },
                        { label: 'Residential', data: [], borderColor: '#f59e0b', borderWidth: 1.5, hidden: true },
                        { label: 'Industry', data: [], borderColor: '#ef4444', borderWidth: 1.5, hidden: true }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        x: { grid: { color: '#131d31' }, ticks: { color: '#64748b', font: { size: 10, family: 'monospace' } } },
                        y: { grid: { color: '#131d31' }, ticks: { color: '#64748b', font: { size: 10, family: 'monospace' } } }
                    },
                    plugins: {
                        legend: { labels: { color: '#94a3b8', boxWidth: 10, font: { size: 11, family: 'sans-serif' } } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${Number(context.raw || 0).toFixed(1)} mA`;
                                }
                            }
                        }
                    }
                }
            });
        }

        function appendChartPoint(p) {
            if (!chart || !p || !p.time) return;
            const labels = chart.data.labels;
            const lastLabel = labels[labels.length - 1];
            const predVal = (p.predicted_current != null ? p.predicted_current : p.total_current);

            if (lastLabel === p.time) {
                const idx = labels.length - 1;
                chart.data.datasets[0].data[idx] = p.total_current;
                chart.data.datasets[1].data[idx] = predVal;
                chart.data.datasets[2].data[idx] = p.hospital || 0;
                chart.data.datasets[3].data[idx] = p.street || 0;
                chart.data.datasets[4].data[idx] = p.house || 0;
                chart.data.datasets[5].data[idx] = p.industry || 0;
                chart.update('none');
                return;
            }

            if (labels.length > 35) {
                labels.shift();
                chart.data.datasets.forEach(d => d.data.shift());
            }
            labels.push(p.time);
            chart.data.datasets[0].data.push(p.total_current);
            chart.data.datasets[1].data.push(predVal);
            chart.data.datasets[2].data.push(p.hospital || 0);
            chart.data.datasets[3].data.push(p.street || 0);
            chart.data.datasets[4].data.push(p.house || 0);
            chart.data.datasets[5].data.push(p.industry || 0);
            chart.update('none');
        }

        // Real-Time Dashboard Updates
        function updateDashboard(data) {
            if (!data) return;
            window.lastTelemetryData = data;

            const isOnline = data.esp32_online === true;
            const hwBadge = document.getElementById('espHwBadge');
            const hwDot = document.getElementById('espHwDot');
            const hwText = document.getElementById('espHwText');
            const liveDot = document.getElementById('liveStatusDot');

            if (hwBadge && hwDot && hwText) {
                if (isOnline) {
                    hwBadge.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/40 text-xs font-mono font-bold text-emerald-300 shadow-sm shadow-emerald-500/20";
                    hwDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
                    hwText.innerText = "ESP32 LIVE HARDWARE";
                    if (liveDot) liveDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
                } else {
                    hwBadge.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs font-mono font-bold text-rose-300";
                    hwDot.className = "w-2 h-2 rounded-full bg-rose-500";
                    hwText.innerText = "ESP32 OFFLINE";
                    if (liveDot) liveDot.className = "w-2 h-2 rounded-full bg-slate-500";
                }
            }

            const limit = data.current_limit || 5000.0;
            const tot_i = isOnline ? (data.total_current || 0.0) : 0.0;
            const pred_i = isOnline ? (data.predicted_current || 0.0) : 0.0;
            const util = isOnline ? (data.utilization || (tot_i / limit * 100.0)) : 0.0;

            // KPIs
            document.getElementById('totCurrentVal').innerText = tot_i.toFixed(1);
            document.getElementById('subPredCurrentText').innerText = isOnline ? `🔮 AI Pred: ${pred_i.toFixed(1)} mA` : `🔮 AI Pred: 0.0 mA (Standby)`;
            document.getElementById('totPowerVal').innerText = (isOnline ? (data.total_power || 0.0) : 0.0).toFixed(2);
            document.getElementById('predictedPowerText').innerText = isOnline ? `🔮 AI Pred: ${(data.predicted_power || 0.0).toFixed(2)} W` : `🔮 AI Pred: 0.00 W (Standby)`;
            document.getElementById('utilPctVal').innerText = util.toFixed(1);
            document.getElementById('utilCapacityBar').style.width = `${Math.min(100, util)}%`;
            document.getElementById('utilCapacityBar').className = util >= 85.0 ? 'bg-rose-500 h-2 rounded-full' : (util >= 75.0 ? 'bg-amber-500 h-2 rounded-full' : 'bg-emerald-500 h-2 rounded-full');
            document.getElementById('headroomText').innerText = `Headroom: ${(100 - util).toFixed(1)}%`;
            document.getElementById('gridLimitText').innerText = `${limit.toFixed(0)} mA`;

            // Status Banner
            const lvl = data.warning_level || 0;
            const banner = document.getElementById('warningBanner');
            const titleEl = document.getElementById('warningTitle');
            const detailEl = document.getElementById('warningDetail');
            const modeBadge = document.getElementById('headerModeBadge');

            if (modeBadge) modeBadge.innerText = data.mode || "DUAL SMPS";

            if (!isOnline) {
                banner.className = "rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/90 border-slate-700 text-slate-300 shadow-lg";
                titleEl.innerHTML = '<span class="text-rose-400 font-bold">⚠️ SYSTEM STANDBY — ESP32 HARDWARE OFFLINE</span>';
                document.getElementById('systemHealthStatus').innerText = "OFFLINE";
                document.getElementById('systemHealthStatus').className = "text-xl sm:text-2xl font-black text-rose-400 font-mono";
                detailEl.innerText = data.warning_message || "Physical ESP32 is powered off or not transmitting. Zero false values displayed. Power on ESP32 to stream live sensor readings.";
            } else {
                if (lvl === 0) {
                    banner.className = "rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-emerald-950/30 border-emerald-800/40 text-emerald-300 shadow-lg";
                    titleEl.innerText = "SYSTEM HEALTHY — LIVE HARDWARE TELEMETRY";
                    document.getElementById('systemHealthStatus').innerText = "HEALTHY";
                    document.getElementById('systemHealthStatus').className = "text-xl sm:text-2xl font-black text-emerald-400 font-mono";
                } else if (lvl === 1) {
                    banner.className = "rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-cyan-950/30 border-cyan-800/40 text-cyan-300 shadow-lg";
                    titleEl.innerText = "LEVEL 1 ADVISORY — MEDIUM LOAD (70%)";
                    document.getElementById('systemHealthStatus').innerText = "ADVISORY";
                    document.getElementById('systemHealthStatus').className = "text-xl sm:text-2xl font-black text-cyan-400 font-mono";
                } else if (lvl === 2) {
                    banner.className = "rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-amber-950/30 border-amber-800/40 text-amber-300 shadow-lg";
                    titleEl.innerText = "LEVEL 2 ALERT — HIGH CAPACITY (80%)";
                    document.getElementById('systemHealthStatus').innerText = "CAPACITY WARNING";
                    document.getElementById('systemHealthStatus').className = "text-xl sm:text-2xl font-black text-amber-400 font-mono";
                } else {
                    banner.className = "rounded-xl p-4 sm:p-5 border transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-rose-950/30 border-rose-800/40 text-rose-300 shadow-lg";
                    titleEl.innerText = "LEVEL 3 CRITICAL — LOAD SHEDDING / FAULT ACTIVE";
                    document.getElementById('systemHealthStatus').innerText = "CRITICAL SHED";
                    document.getElementById('systemHealthStatus').className = "text-xl sm:text-2xl font-black text-rose-400 font-mono";
                }
                detailEl.innerText = data.warning_message || "Grid operating within 2-SD limits. 15s anti-chattering dwell active.";
            }

            // Sources Deck
            const sources = isOnline ? (data.sources || {}) : { smps1: false, smps2: false, battery: false };
            const updateSourceCard = (cardId, dotId, badgeId, isSrcOnline, text) => {
                const dot = document.getElementById(dotId);
                const badge = document.getElementById(badgeId);
                if (dot) dot.className = isSrcOnline ? "w-3 h-3 rounded-full bg-emerald-400 animate-pulse" : "w-3 h-3 rounded-full bg-slate-500";
                if (badge) {
                    badge.innerText = isSrcOnline ? "ONLINE" : (text || "OFFLINE");
                    badge.className = isSrcOnline ? "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700";
                }
            };
            updateSourceCard('cardSmps1', 'dotSmps1', 'badgeSmps1', sources.smps1);
            updateSourceCard('cardSmps2', 'dotSmps2', 'badgeSmps2', sources.smps2);
            updateSourceCard('cardBattery', 'dotBattery', 'badgeBattery', sources.battery);

            // Load Cards
            let onlineCount = 0;
            const loadPrefixMap = {
                'hospital': 'hosp',
                'street': 'strt',
                'house': 'hous',
                'industry': 'indu'
            };
            const loadBtnMap = {
                'hospital': 'btnRelayHosp',
                'street': 'btnRelayStrt',
                'house': 'btnRelayHous',
                'industry': 'btnRelayIndu'
            };

            ['hospital', 'street', 'house', 'industry'].forEach(l => {
                const info = data[l] || {};
                const r = info.relay !== undefined ? info.relay : 1;
                if (isOnline && r === 1) onlineCount++;

                const pfx = loadPrefixMap[l] || (l === 'street' ? 'strt' : l.slice(0, 4));
                const btnId = loadBtnMap[l] || (l === 'street' ? 'btnRelayStrt' : `btnRelay${l.charAt(0).toUpperCase() + l.slice(1, 4)}`);

                const currEl = document.getElementById(`${pfx}Curr`) || document.getElementById(`${l.slice(0, 4)}Curr`);
                const pwrEl = document.getElementById(`${pfx}Power`) || document.getElementById(`${l.slice(0, 4)}Power`);
                const btn = document.getElementById(btnId) || document.getElementById(`btnRelay${l.charAt(0).toUpperCase() + l.slice(1, 4)}`);
                const badge = document.getElementById(`${pfx}StatusBadge`) || document.getElementById(`${l.slice(0, 4)}StatusBadge`);

                const isLoadActive = isOnline && r === 1 && (info.current || 0) >= 15.0;
                if (currEl) currEl.innerText = isLoadActive ? `${(info.current || 0).toFixed(1)} mA` : `0.0 mA`;
                if (pwrEl) pwrEl.innerText = isLoadActive ? `${(((info.current || 0) * 12.0) / 1000.0).toFixed(2)} W` : (r === 0 ? `0.00 W (OFF)` : `0.00 W`);
                if (btn) {
                    btn.innerText = r === 1 ? "ON (Active)" : "OFF (Standby)";
                    btn.className = r === 1
                        ? "mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-sm"
                        : "mt-3 w-full py-1.5 rounded-lg text-xs font-bold bg-grid-800 hover:bg-grid-750 text-slate-400 transition active:scale-95 border border-grid-700";
                }
                if (badge) {
                    if (!isOnline) {
                        badge.innerText = "OFFLINE";
                        badge.className = "text-slate-400 font-bold";
                    } else if (r === 0) {
                        badge.innerText = "SHED (OFF)";
                        badge.className = "text-slate-400 font-bold";
                    } else if ((info.current || 0) < 15.0) {
                        badge.innerText = "NO LOAD";
                        badge.className = "text-amber-400 font-bold";
                    } else {
                        badge.innerText = info.status || "NORMAL";
                        badge.className = info.status === "NORMAL" ? "text-emerald-400 font-bold" : "text-rose-400 font-bold";
                    }
                }
            });

            // Critical Load Card
            const crit = data.critical || {};
            const critCurrEl = document.getElementById('critCurrVal');
            const critPwrEl = document.getElementById('critPowerVal');
            if (critCurrEl) critCurrEl.innerText = isOnline ? `${(crit.current || 0).toFixed(1)} mA` : `0.0 mA`;
            if (critPwrEl) critPwrEl.innerText = isOnline ? `${((crit.current || 0) * 12.0 / 1000.0).toFixed(2)} W (12.0V)` : `0.00 W (OFFLINE)`;

            document.getElementById('systemHealthDesc').innerText = isOnline
                ? `${onlineCount}/4 Normal Loads Active • 0 Hardware Trips`
                : `0 Active Loads • Physical ESP32 Powered Off or Disconnected`;

            // Digital Twin SVG
            updateDigitalTwin(data);

            // Prediction Breakdown
            if (data.prediction_breakdown) {
                renderPredictionBreakdown(data.prediction_breakdown);
            }

            // Events
            if (data.events) {
                renderEventsTable(data.events);
            }
        }

        // Digital Twin SVG updates
        function updateDigitalTwin(data) {
            const isOnline = data.esp32_online === true;
            const sources = isOnline ? (data.sources || {}) : { smps1: false, smps2: false, battery: false };
            const setLed = (id, on) => {
                const el = document.getElementById(id);
                if (el) el.setAttribute('fill', on ? '#10b981' : '#64748b');
            };
            setLed('ledSmps1', sources.smps1);
            setLed('ledSmps2', sources.smps2);
            setLed('ledBattery', sources.battery);

            // Dynamic Feeder Power Flow Paths from sources to 12V busbar
            const setSourcePath = (id, active) => {
                const el = document.getElementById(id);
                if (el) {
                    el.setAttribute('class', active ? 'flow-active' : '');
                    el.setAttribute('stroke', active ? '#0ea5e9' : '#475569');
                    el.setAttribute('stroke-width', active ? '2' : '1.5');
                }
            };
            setSourcePath('pathSmps1', sources.smps1);
            setSourcePath('pathSmps2', sources.smps2);
            setSourcePath('pathBattery', sources.battery);

            const updateBreaker = (swId, lineId, boxId, r, status) => {
                const sw = document.getElementById(swId);
                const line = document.getElementById(lineId);
                const box = document.getElementById(boxId);
                const isTripped = (status === 'OVERCURRENT' || status === 'TRIPPED' || status === 'SHED');
                if (sw) {
                    sw.setAttribute('y2', (isOnline && r === 1) ? '10' : '-2');
                    sw.setAttribute('stroke', (isOnline && r === 1) ? '#10b981' : '#ef4444');
                }
                if (line) {
                    line.setAttribute('class', (isOnline && r === 1 && !isTripped) ? 'flow-active' : '');
                    line.setAttribute('stroke', (isOnline && r === 1) ? '#0ea5e9' : '#475569');
                }
                if (box) {
                    box.setAttribute('stroke', isOnline ? (status === 'OVERCURRENT' ? '#ef4444' : (r === 1 ? '#0284c7' : '#334155')) : '#334155');
                }
            };

            const h = data.hospital || {}; updateBreaker('dtSwHosp', 'dtLineHosp', 'dtBoxHosp', h.relay, h.status);
            const s = data.street || {}; updateBreaker('dtSwStrt', 'dtLineStrt', 'dtBoxStrt', s.relay, s.status);
            const ho = data.house || {}; updateBreaker('dtSwHous', 'dtLineHous', 'dtBoxHous', ho.relay, ho.status);
            const ind = data.industry || {}; updateBreaker('dtSwIndu', 'dtLineIndu', 'dtBoxIndu', ind.relay, ind.status);

            const c = data.critical || {};
            const dtCrit = document.getElementById('dtCritCurr');
            if (dtCrit) dtCrit.innerText = isOnline ? `${(c.current || 0).toFixed(1)} mA • PROTECTED` : `0.0 mA • OFFLINE`;

            const dtHosp = document.getElementById('dtHospCurr');
            if (dtHosp) {
                const val = (isOnline && h.relay === 1) ? (h.current || 0).toFixed(1) : '0.0';
                dtHosp.innerText = isOnline ? `${val} mA • ${h.relay === 1 ? 'GPIO14' : 'SHED'}` : `0.0 mA • OFFLINE`;
                dtHosp.setAttribute('fill', (isOnline && h.relay === 1) ? '#93c5fd' : '#64748b');
            }

            const dtStrt = document.getElementById('dtStrtCurr');
            if (dtStrt) {
                const val = (isOnline && s.relay === 1) ? (s.current || 0).toFixed(1) : '0.0';
                dtStrt.innerText = isOnline ? `${val} mA • ${s.relay === 1 ? 'GPIO13' : 'SHED'}` : `0.0 mA • OFFLINE`;
                dtStrt.setAttribute('fill', (isOnline && s.relay === 1) ? '#6ee7b7' : '#64748b');
            }

            const dtHous = document.getElementById('dtHousCurr');
            if (dtHous) {
                const val = (isOnline && ho.relay === 1) ? (ho.current || 0).toFixed(1) : '0.0';
                dtHous.innerText = isOnline ? `${val} mA • ${ho.relay === 1 ? 'GPIO4' : 'SHED'}` : `0.0 mA • OFFLINE`;
                dtHous.setAttribute('fill', (isOnline && ho.relay === 1) ? '#fcd34d' : '#64748b');
            }

            const dtIndu = document.getElementById('dtInduCurr');
            if (dtIndu) {
                const val = (isOnline && ind.relay === 1) ? (ind.current || 0).toFixed(1) : '0.0';
                dtIndu.innerText = isOnline ? `${val} mA • ${ind.relay === 1 ? 'GPIO26' : 'SHED'}` : `0.0 mA • OFFLINE`;
                dtIndu.setAttribute('fill', (isOnline && ind.relay === 1) ? '#fda4af' : '#64748b');
            }

            // Summary metrics
            const tot_i = isOnline ? (data.total_current || 0.0) : 0.0;
            const limit = data.current_limit || 5000.0;
            const util = isOnline ? (data.utilization !== undefined ? data.utilization : (tot_i / limit * 100.0)) : 0.0;
            const dtTot = document.getElementById('dtSummaryTotal');
            if (dtTot) dtTot.innerText = `${tot_i.toFixed(1)} mA`;
            const dtLim = document.getElementById('dtSummaryLimit');
            if (dtLim) dtLim.innerText = `${limit.toFixed(0)} mA`;
            const dtUt = document.getElementById('dtSummaryUtil');
            if (dtUt) {
                dtUt.innerText = `${util.toFixed(1)}%`;
                dtUt.setAttribute('fill', util >= 85.0 ? '#ef4444' : (util >= 70.0 ? '#f59e0b' : '#10b981'));
            }
            const dtHead = document.getElementById('dtSummaryHeadroom');
            if (dtHead) dtHead.innerText = isOnline ? `${Math.max(0, (limit * 0.84) - tot_i).toFixed(0)} mA` : `${(limit * 0.84).toFixed(0)} mA`;

            // Dynamic Online Breakers count
            let onlineBreakers = 0;
            if (isOnline) {
                ['hospital', 'street', 'house', 'industry'].forEach(l => {
                    if (data[l] && data[l].relay === 1) onlineBreakers++;
                });
            }
            const dtBreak = document.getElementById('dtSummaryBreakers');
            if (dtBreak) {
                dtBreak.innerText = isOnline ? `${onlineBreakers} / 4 Active` : `0 / 4 Offline`;
                dtBreak.setAttribute('fill', isOnline ? (onlineBreakers === 4 ? '#10b981' : (onlineBreakers >= 2 ? '#f59e0b' : '#ef4444')) : '#64748b');
            }
        }

        // Render AI Breakdown Cards with Arrows
        function renderPredictionBreakdown(bd) {
            const container = document.getElementById('predBranchBreakdown');
            if (!container) return;
            const isOnline = window.lastTelemetryData && window.lastTelemetryData.esp32_online === true;
            if (!isOnline) {
                container.innerHTML = `
                    <div class="col-span-full p-4 rounded-lg bg-grid-950/60 border border-grid-800 text-center text-xs text-slate-400 font-mono">
                        📡 ESP32 hardware offline — connect/power ESP32 to stream physical telemetry and compute live ML branch predictions.
                    </div>
                `;
                return;
            }
            container.innerHTML = "";
            for (const [key, val] of Object.entries(bd)) {
                const card = document.createElement('div');
                const isHealthy = val.is_healthy;
                const isOn = val.on === 1;
                card.className = `p-3 rounded-lg border text-xs font-mono flex flex-col justify-between ${
                    isOn ? (isHealthy ? 'bg-grid-950/90 border-indigo-500/40 text-indigo-200' : 'bg-rose-950/30 border-rose-600 text-rose-300')
                         : 'bg-grid-950/60 border-grid-800 text-slate-500'
                }`;
                card.innerHTML = `
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-bold text-[11px] text-white font-sans">${val.name}</span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded ${isOn ? (isHealthy ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300') : 'bg-slate-800 text-slate-400'}">${isOn ? 'ON' : 'OFF'}</span>
                    </div>
                    <div class="font-black text-sm my-1">${val.predicted_current.toFixed(1)} mA</div>
                    <div class="text-[9px] text-slate-400 truncate mt-0.5">&rarr; ${val.reason}</div>
                `;
                container.appendChild(card);
            }
        }

        // Render Events Table
        function renderEventsTable(events) {
            const tbody = document.getElementById('eventsTableBody');
            if (!tbody) return;
            tbody.innerHTML = "";
            events.slice(0, 10).forEach(e => {
                const tr = document.createElement('tr');
                const badgeColor = e.action_type === 'TRIP' ? 'text-rose-400 font-bold' : (e.action_type === 'SHED' ? 'text-amber-400 font-bold' : 'text-emerald-400 font-bold');
                tr.innerHTML = `
                    <td class="p-2.5 text-slate-400">${e.timestamp.slice(11)}</td>
                    <td class="p-2.5 ${badgeColor}">${e.action_type}</td>
                    <td class="p-2.5 text-white">${(e.load_name || '').toUpperCase()}</td>
                    <td class="p-2.5 text-slate-300">${e.reason || ''}</td>
                    <td class="p-2.5 text-cyan-400">${(e.current_mA || 0).toFixed(0)} mA</td>
                    <td class="p-2.5 text-slate-400">${(e.limit_mA || 0).toFixed(0)} mA</td>
                    <td class="p-2.5 text-slate-500 truncate max-w-xs">${e.details || ''}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function appendDecisionLog(text) {
            const list = document.getElementById('decisionExplanationList');
            if (!list) return;
            const item = document.createElement('div');
            item.className = "text-slate-300 p-2.5 rounded bg-grid-950 border border-grid-800/80 leading-relaxed";
            item.innerText = text;
            list.insertBefore(item, list.firstChild);
            if (list.children.length > 6) list.removeChild(list.lastChild);
        }

        // Relay Control & Modal Confirmation
        async function sendRelayCommand(load, state) {
            if (window.lastTelemetryData && window.lastTelemetryData[load]) {
                window.lastTelemetryData[load].relay = state;
                if (state === 0) {
                    window.lastTelemetryData[load].current = 0.0;
                    window.lastTelemetryData[load].power = 0.0;
                    window.lastTelemetryData[load].status = "SHED";
                } else {
                    const defs = { hospital: 252.0, street: 391.0, house: 238.0, industry: 236.0 };
                    window.lastTelemetryData[load].current = defs[load] || 240.0;
                    window.lastTelemetryData[load].power = ((defs[load] || 240.0) * 12.0 / 1000.0);
                    window.lastTelemetryData[load].status = "NORMAL";
                }
                let tot = window.lastTelemetryData.critical ? (window.lastTelemetryData.critical.current || 298.5) : 298.5;
                ['hospital', 'street', 'house', 'industry'].forEach(l => {
                    if (window.lastTelemetryData[l] && window.lastTelemetryData[l].relay === 1) {
                        tot += window.lastTelemetryData[l].current || 0;
                    }
                });
                window.lastTelemetryData.total_current = tot;
                window.lastTelemetryData.total_power = tot * 12.0 / 1000.0;
                const lim = window.lastTelemetryData.current_limit || 5000.0;
                window.lastTelemetryData.utilization = (tot / lim) * 100.0;
                updateDashboard(window.lastTelemetryData);
            }
            try {
                const res = await fetch('/api/relay/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ load: load, state: state })
                });
                if (res.ok) {
                    const result = await res.json();
                    if (result.data) {
                        updateDashboard(result.data);
                    }
                }
            } catch (e) {}
        }

        function promptRelayToggle(load) {
            const loadBtnMap = {
                'hospital': 'btnRelayHosp',
                'street': 'btnRelayStrt',
                'house': 'btnRelayHous',
                'industry': 'btnRelayIndu'
            };
            const btnId = loadBtnMap[load] || (load === 'street' ? 'btnRelayStrt' : `btnRelay${load.charAt(0).toUpperCase() + load.slice(1, 4)}`);
            const btn = document.getElementById(btnId) || document.getElementById(`btnRelay${load.charAt(0).toUpperCase() + load.slice(1, 4)}`);
            const curState = (btn && btn.innerText.includes("ON")) ? 1 : 0;
            const targetState = curState === 1 ? 0 : 1;

            if (currentMode === "MANUAL") {
                pendingLoad = load;
                pendingState = targetState;
                document.getElementById('confirmModalText').innerText =
                    `Confirm switching ${load.toUpperCase()} breaker from ${curState === 1 ? 'ON' : 'OFF'} to ${targetState === 1 ? 'ON' : 'OFF'}?`;
                document.getElementById('confirmModal').classList.remove('hidden');
            } else {
                sendRelayCommand(load, targetState);
            }
        }

        function closeConfirmModal() {
            document.getElementById('confirmModal').classList.add('hidden');
            pendingLoad = null;
            pendingState = null;
        }

        function executeRelayToggle() {
            if (pendingLoad) {
                sendRelayCommand(pendingLoad, pendingState);
            }
            closeConfirmModal();
        }

        function setMode(mode) {
            fetch('/api/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode })
            }).then(r => r.json()).then(d => {
                if (d.success) applyModeState(d.control_mode);
            });
        }

        function applyModeState(mode) {
            currentMode = mode;
            const isAuto = mode === "AUTO";
            document.getElementById('btnAutoMode').className = isAuto
                ? "px-2.5 py-1 rounded-md bg-blue-600 text-white transition shadow-sm font-bold flex items-center gap-1.5"
                : "px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition font-medium flex items-center gap-1.5";
            document.getElementById('btnManualMode').className = !isAuto
                ? "px-2.5 py-1 rounded-md bg-amber-600 text-white transition shadow-sm font-bold flex items-center gap-1.5"
                : "px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition font-medium flex items-center gap-1.5";
        }

        // WebSocket & Polling Engine
        function connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws/telemetry`);

            ws.onopen = () => {
                document.getElementById('liveStatusDot').className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                lastSyncTimestamp = Date.now();
                if (msg.type === "init") {
                    updateDashboard(msg.telemetry);
                    if (msg.history && Array.isArray(msg.history)) {
                        msg.history.forEach(p => appendChartPoint(p));
                    }
                } else if (msg.type === "telemetry") {
                    updateDashboard(msg.data);
                    if (msg.point && msg.data && msg.data.esp32_online) appendChartPoint(msg.point);
                } else if (msg.type === "mode") {
                    applyModeState(msg.mode);
                } else if (msg.type === "action") {
                    appendDecisionLog(msg.event);
                    fetchEvents();
                }
            };

            ws.onclose = () => {
                document.getElementById('liveStatusDot').className = "w-2 h-2 rounded-full bg-cyan-400";
                setTimeout(connectWebSocket, 2000);
            };
        }

        async function fetchLatestTelemetry() {
            try {
                const res = await fetch('/api/status');
                if (!res.ok) return;
                const data = await res.json();
                if (data && data.timestamp) {
                    updateDashboard(data);
                    // Only append to rolling chart when real ESP32 hardware is actively streaming
                    if (data.esp32_online) {
                        appendChartPoint({
                            time: data.timestamp ? String(data.timestamp).slice(-8) : '',
                            total_current: Number(data.total_current || 0),
                            predicted_current: Number(data.predicted_current != null ? data.predicted_current : data.total_current),
                            hospital: Number(data.hospital ? data.hospital.current : 0),
                            street: Number(data.street ? data.street.current : 0),
                            house: Number(data.house ? data.house.current : 0),
                            industry: Number(data.industry ? data.industry.current : 0)
                        });
                    }
                }
            } catch (e) {}
        }

        async function fetchEvents() {
            try {
                const res = await fetch('/api/events');
                if (!res.ok) return;
                const events = await res.json();
                if (Array.isArray(events)) {
                    renderEventsTable(events);
                }
            } catch (e) {}
        }

        async function doForcedRefresh() {
            if (isFetching) return;
            isFetching = true;
            const timerEl = document.getElementById('countdownTimer');
            if (timerEl) timerEl.innerText = 'Syncing...';
            try {
                await Promise.allSettled([fetchLatestTelemetry(), fetchEvents()]);
            } catch (e) {
            } finally {
                lastSyncTimestamp = Date.now();
                isFetching = false;
                if (timerEl) timerEl.innerText = '2s';
            }
        }

        function forceRefresh() {
            doForcedRefresh();
        }

        // Ticking loop running every second
        setInterval(() => {
            const now = Date.now();
            const elapsed = Math.floor((now - lastSyncTimestamp) / 1000);
            const remaining = Math.max(0, 2 - elapsed);
            const timerEl = document.getElementById('countdownTimer');
            if (timerEl && !isFetching) {
                timerEl.innerText = `${remaining}s`;
            }
            if (elapsed >= 2 && !isFetching) {
                doForcedRefresh();
            }
        }, 1000);

        window.addEventListener('DOMContentLoaded', async () => {
            initChart();
            connectWebSocket();
            try {
                const res = await fetch('/api/history');
                if (res.ok) {
                    const history = await res.json();
                    if (Array.isArray(history) && history.length > 0) {
                        history.forEach(p => appendChartPoint(p));
                    }
                }
            } catch (e) {}
            doForcedRefresh();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run("grid_dashboard:app", host=config.scada_host, port=config.scada_port, reload=False)

