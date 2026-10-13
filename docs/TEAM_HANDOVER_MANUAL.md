# ⚡ SMART GRID REAL-TIME AUTONOMOUS CONTROLLER & SCADA SUITE ⚡
### Complete Project Handover & Technical Documentation Manual
**Author & Lead Engineer:** Saptarshi Das  
**Date:** September 2026  
**System Version:** 2.0.0 (High-Speed 2-Second Closed-Loop Architecture)

---

## 🌟 Executive Summary
This project is an **Autonomous, Edge-to-Cloud Smart Microgrid Management System**. It dynamically balances power generation against varying electrical loads, prevents transformer burnouts, detects physical circuit faults using Machine Learning, provides autonomous self-healing load restoration, and enables worldwide SCADA monitoring and smartphone alerting.

The system combines:
1. **Physical Hardware / Edge Computing**: ESP32 microcontroller reading dual I2C buses with INA219 current/voltage sensors and 4-channel relay modules.
2. **Artificial Intelligence & Closed-Loop Control**: Python daemon running Scikit-Learn models for load forecasting and branch diagnostics.
3. **Capacity Protection & Self-Healing**: Greedy priority-packing algorithm with strict 15-second anti-chattering protection.
4. **Cloud SCADA Dashboard**: FastAPI web server with real-time WebSockets, local Wi-Fi hosting, and Cloudflare HTTPS worldwide tunneling.
5. **Real-Time Push Notifications**: Instant Telegram bot alerts for emergency trips, load sheds, restorations, and live telemetry cards.

---

## 📂 Project Directory Structure

```text
SMART_GRID_PROJECT_PACKAGE/
│
├── run_smart_grid_suite.py        # 🚀 Master One-Click Launcher (Starts Dashboard, Tunnel & AI)
├── smart_grid_ai.py               # 🧠 Python AI Closed-Loop Controller & ML Inference Engine
├── grid_dashboard.py              # 🌐 SCADA Web Server (FastAPI + WebSockets + Interactive UI)
├── grid_alerts.py                 # 📱 Async Telegram Notification Engine (HTML Formatting)
├── grid_analytics.py              # 📊 Energy & IEEE Metric Analytics / PDF Report Generator
├── alert_config.json              # 🔑 Telegram Bot Token & Chat ID Configuration
├── live_smartgrid.db              # 🗄️ SQLite Database (Telemetry logs, audit trails, faults)
├── cloudflared.exe                # 🌐 Cloudflare Tunnel Daemon for public HTTPS URLs
├── requirements.txt               # 📦 Python Package Dependencies
│
├── models/                        # 🤖 Machine Learning Pre-Trained Models (.pkl)
│   ├── load_forecasting_current_model.pkl
│   ├── load_forecasting_power_model.pkl
│   ├── fault_detection_model.pkl
│   ├── fault_load_model.pkl
│   ├── fault_type_model.pkl
│   ├── fault_severity_model.pkl
│   ├── forecasting_features.pkl
│   ├── model_hospital.pkl
│   ├── model_street.pkl
│   ├── model_house.pkl
│   └── model_industry.pkl
│
├── smartgrid_closed_loop_esp32/   # 🔌 Arduino / ESP32 Embedded Firmware
│   └── smartgrid_closed_loop_esp32.ino
│
└── README.md                      # 📖 This Complete Documentation & Handover Guide
```

---

## 🔌 Hardware Circuit & Power Topology

### 1. Power Sources & Capacity Limits
* **Dual SMPS (Primary Grid Mode)**: $5000	ext{ mA}$ limit ($60	ext{ W}$ at $12	ext{ V}$). Full operation for all loads.
* **Single SMPS (Degraded Mode)**: $1000	ext{ mA}$ limit ($12	ext{ W}$ at $12	ext{ V}$). Priority shedding enforced.
* **Battery (Emergency Standby)**: $800	ext{ mA}$ limit ($9.6	ext{ W}$ at $12	ext{ V}$). Emergency critical branches only.

### 2. Load Branches & Priority Hierarchy
| Branch | Nominal Draw | 2-SD Overcurrent Trip Limit | Shedding Priority | Reconnection Priority | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Critical Load** | $300	ext{ mA}$ ($3.6	ext{ W}$) | $> 320.0	ext{ mA}$ | **Never Shed (Fixed)** | Fixed | Infrastructure, controls & base loads |
| **Hospital** | $256	ext{ mA}$ ($3.1	ext{ W}$) | $> 272.0	ext{ mA}$ | Priority 4 (Last to shed) | **Priority 1 (First to restore)** | Life-support & medical branch |
| **Street Lights** | $394	ext{ mA}$ ($4.7	ext{ W}$) | $> 405.0	ext{ mA}$ | Priority 3 | Priority 2 | Public infrastructure & safety |
| **Residential (House)**| $241	ext{ mA}$ ($2.9	ext{ W}$) | $> 256.0	ext{ mA}$ | Priority 2 | Priority 3 | Residential residential branch |
| **Industry** | $240	ext{ mA}$ ($2.9	ext{ W}$) | $> 264.0	ext{ mA}$ | **Priority 1 (First to shed)** | Priority 4 (Last to restore) | Non-essential commercial / heavy power |

---

## 🧠 Software Architecture & Data Flow

1. **Edge Telemetry Acquisition**:
   - ESP32 reads 5 INA219 current/voltage sensors across dual I2C buses every **$1	ext{ second}$**.
   - Assembles JSON payload with hardware states and publishes to HiveMQ Cloud broker topic: `smartgrid/live`.
2. **AI Inference & Autonomous Controller**:
   - Python controller (`smart_grid_ai.py`) processes incoming MQTT packets at a **$2	ext{-second}$ sync rate**.
   - Evaluates machine learning models to forecast future power/current and detect branch anomalies.
   - Computes dynamic load-aware predictions considering active relays and fault isolation.
3. **Protection & Self-Healing Decision Engine**:
   - **Emergency Overcurrent**: If current exceeds $2	ext{-SD}$ limit, isolates relay in $<1	ext{s}$.
   - **Capacity Overload Shedding**: If total current reaches $\ge 85\%$ of source capacity, sheds lowest priority load.
   - **Priority-Preserving Packing**: If utilization is below $84\%$ (e.g. $57\%$), evaluates highest priority load that fits without exceeding $84\%$. Bypasses large loads (Street) to restore fitting priority loads (House).
   - **Anti-Chattering Timers**: Enforces strict $15	ext{-second}$ settling dwell times for all relay energization, de-energization, and source transitions.
4. **SCADA Web SCADA**:
   - FastAPI server hosts local dashboard at `http://localhost:8000`.
   - Cloudflare tunnel provides secure public HTTPS access worldwide (`https://....trycloudflare.com`).
   - WebSockets push real-time updates every 2 seconds without page refreshes.
5. **Instant Push Alerting**:
   - Background worker in `grid_alerts.py` pushes clean HTML-formatted telemetry cards and priority alerts directly to Telegram smartphones.

---

## 🛠️ Complete Engineering Journey: Problems Faced & How They Were Solved

This section documents every technical challenge overcome during development — crucial for presentations, defense, and reviews:

### Problem 1: Telegram Ping Test Succeeded, but Real Grid Events Were Dropped
* **Root Cause**: `send_telegram_message()` was configured with Telegram's legacy `parse_mode: "Markdown"`. When sending real events, strings contained underscores (e.g. `TRIP_HOSPITAL`, `OVERLOAD_85`, `RELAY_ON_NO_CURRENT`). In Markdown, unmatched underscores are treated as opening italic markup. Telegram rejected these requests with `HTTP 400 Bad Request: can't parse entities`.
* **Solution**: Upgraded the notification engine to `parse_mode: "HTML"` with `html.escape()` sanitization. HTML tags (`<b>`, `<code>`, `<i>`) are completely immune to underscore syntax collisions.

### Problem 2: Synchronous Network Latency Freezing the MQTT Loop
* **Root Cause**: Sending HTTP requests to `https://api.telegram.org` took $200	ext{–}500	ext{ ms}$. If Wi-Fi lagged, this synchronous delay caused the main MQTT loop in `smart_grid_ai.py` to miss packets.
* **Solution**: Implemented a non-blocking asynchronous queue (`queue.Queue`) and background worker thread in `grid_alerts.py`. Telemetry and alerts are queued in $<0.1	ext{ ms}$ and transmitted in the background without impacting controller loop timing.

### Problem 3: Grid Stranded at ~57% Capacity After Power Source Drops
* **Root Cause**: When switching from Dual SMPS ($5000	ext{ mA}$) to Single SMPS ($1000	ext{ mA}$), shedding occurred and utilization dropped to $\sim 57\%$ ($570	ext{ mA}$). The old restoration code checked candidates sequentially without fallback and capped restoration at $<80\%$. Because the next candidate in priority, Street ($394	ext{ mA}$), would reach $96.4\%$, the old loop stopped immediately. It never evaluated whether House ($241	ext{ mA}$) could fit!
* **Solution**: Implemented **Priority-Preserving Best-Fit / Greedy Packing**. If a candidate would push the grid above $84.0\%$, the system does not stop; it bypasses that candidate, logs the reason, and evaluates the next priority candidate. In this scenario, House is restored, safely packing the grid to **$\mathbf{81.1\%}$**.

### Problem 4: Relay Chattering & Oscillation
* **Root Cause**: Rapid switching cycles between capacity shedding and restoration can cause relay chattering, damaging physical contacts.
* **Solution**: Introduced a multi-layered anti-chattering timing architecture:
  1. **$15	ext{s}$ Minimum ON Dwell**: Once a load is turned ON, it cannot be shed for at least 15s.
  2. **$15	ext{s}$ Minimum OFF Dwell**: Once a load is turned OFF, it cannot be restored for at least 15s.
  3. **$15	ext{s}$ Source Drop Hold**: Dropping capacity limit pauses all restorations for 15s.
  4. **$1.0\%$ ($10	ext{ mA}$) Hysteresis Deadband**: Shedding trips at $\ge 85.0\%$, while restoration caps at $\le 84.0\%$.

### Problem 5: Offline Startup & Network Disconnect Crashes
* **Root Cause**: If the laptop or ESP32 booted without active Wi-Fi, `mqtt.connect()` crashed with `socket.gaierror`.
* **Solution**: Wrapped the MQTT connection in a non-blocking auto-retry loop with background reconnect workers. The dashboard starts locally at `http://localhost:8000` immediately, and the ESP32 switches to autonomous local edge protection.

### Problem 6: NameError: name 'threading' is not defined in Dashboard
* **Root Cause**: When upgrading the web server to connect to MQTT asynchronously in a daemon thread, `import threading` was missing from `grid_dashboard.py`.
* **Solution**: Added `import threading` to the module imports and synchronized across all directories.

---

## 🚀 Teammates' Step-by-Step Quickstart Guide

### 1. Prerequisites
- **Operating System**: Windows, Linux, or macOS.
- **Python**: Version 3.10 or higher.
- **Hardware (Optional for simulation)**: ESP32 development board with INA219 sensors and 4-relay board.

### 2. Installation
Open Command Prompt / PowerShell inside this folder and run:
```powershell
pip install -r requirements.txt
```

### 3. Running the Entire System (One Command)
Run the master suite launcher:
```powershell
python run_smart_grid_suite.py
```
This launcher automatically:
1. Starts the SCADA Web Dashboard on port 8000.
2. Provisions a public worldwide HTTPS link via Cloudflare Tunnel.
3. Initializes the Python AI closed-loop controller, ML models, and Telegram alerting engine.

### 4. Viewing the System
- **Local Browser**: Navigate to `http://localhost:8000`
- **Mobile / Remote**: Open the Cloudflare public URL printed in the console.
- **Telegram Bot**: Open Telegram and chat with your bot to receive real-time telemetry status cards and instant event alerts.

---

## 🏆 Project Achievements & Features for Viva
- **IEEE-Style Analytics**: Live Loss of Load Probability (LOLP), SAIDI/SAIFI reliability metrics, and instant PDF/CSV reporting.
- **Sub-Second Edge Protection**: Local hardware isolation on ESP32 in $<1	ext{s}$ even if the laptop is powered off.
- **Machine Learning**: 11 pre-trained scikit-learn models performing predictive load forecasting and multi-class fault classification.
- **Zero Popup Windows**: All background daemons run silently via unified threading.
