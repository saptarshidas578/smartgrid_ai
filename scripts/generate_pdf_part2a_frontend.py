import os
import sys
import shutil
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        if self._pageNumber > 1:
            self.drawString(54, 755, "Smart Grid AI — Part 2A: Front End & SCADA Presentation Layer")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(54, 32, "Vellore Institute of Technology (VIT) | Saptarshi Das | saptarshidas578/smartgrid_ai")
        self.restoreState()

def build_part2a_pdf(output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle('T', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'), spaceAfter=5)
    sub_s = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#475569'), spaceAfter=12)
    h1_s = ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#1E3A8A'), spaceBefore=12, spaceAfter=5, keepWithNext=True)
    h2_s = ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=3, keepWithNext=True)
    body_s = ParagraphStyle('B', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#1E293B'), spaceAfter=4)
    bullet_s = ParagraphStyle('Bul', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11.5, textColor=colors.HexColor('#1E293B'), leftIndent=12, firstLineIndent=-8, spaceAfter=2.5)
    code_s = ParagraphStyle('C', parent=styles['Normal'], fontName='Courier', fontSize=7, leading=9.2, textColor=colors.HexColor('#0F172A'))

    def code_box(code_text):
        p = Preformatted(code_text.strip(), code_s)
        b = Table([[p]], colWidths=[504])
        b.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        return b

    def add_chunk(title, code_str, bullets):
        c_items = []
        c_items.append(Paragraph(title, h2_s))
        c_items.append(code_box(code_str))
        c_items.append(Spacer(1, 4))
        for b in bullets:
            c_items.append(Paragraph(b, bullet_s))
        c_items.append(Spacer(1, 6))
        return KeepTogether(c_items)

    story = []

    # Title & Metadata Card
    story.append(Paragraph("PART 2A: The Front End & Presentation Layer", title_s))
    story.append(Paragraph("Complete Technical Architecture, Full-Stack SCADA Implementation & Detailed Code Dissection", sub_s))
    
    meta_data = [
        [
            Paragraph("<b>Author:</b> Saptarshi Das (VIT Vellore)<br/><b>Email:</b> saptarshid234@outlook.com<br/><b>Repository:</b> saptarshidas578/smartgrid_ai", body_s),
            Paragraph("<b>Primary Modules:</b> <code>src/dashboard/grid_dashboard.py</code><br/><b>Services:</b> <code>grid_analytics.py, telegram_service.py</code><br/><b>Role:</b> Web SCADA, WebSockets, Reporting & Alerts", body_s)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Front-End Architecture & Design Philosophy", h1_s))
    story.append(Paragraph(
        "Part 2A constitutes the human-facing operational tier of the smart grid. "
        "It provides plant supervisors and electrical engineers with complete situational awareness, telemetry visualization, "
        "manual control overrides, and automated reporting. Built on an asynchronous <b>FastAPI</b> web server, "
        "the presentation tier pushes real-time telemetry over WebSockets at $1.0\\text{ Hz}$, eliminating polling latency "
        "while guaranteeing that UI operations remain strictly non-blocking to the underlying power safety loop.",
        body_s
    ))

    # Component Table
    front_table_data = [
        [Paragraph("<b>Component</b>", body_s), Paragraph("<b>Underlying Stack</b>", body_s), Paragraph("<b>Protocol / Channel</b>", body_s), Paragraph("<b>Operator Capability</b>", body_s)],
        [Paragraph("SCADA Web UI", body_s), Paragraph("FastAPI + HTML5/CSS3/JS", body_s), Paragraph("HTTP (Port 8000) / WebSockets", body_s), Paragraph("Live telemetry, dynamic gauges, status badges, manual relay switches", body_s)],
        [Paragraph("WebSocket Stream", body_s), Paragraph("Asyncio WebSocket Server", body_s), Paragraph("<code>/ws/telemetry</code> (1 Hz)", body_s), Paragraph("Zero-refresh live streaming of currents, voltages, powers, and alarms", body_s)],
        [Paragraph("Analytics Engine", body_s), Paragraph("Matplotlib + Pandas", body_s), Paragraph("On-Demand REST API", body_s), Paragraph("Generates energy pie charts, daily load profiles, voltage stability curves", body_s)],
        [Paragraph("Executive Reporter", body_s), Paragraph("ReportLab Platypus Engine", body_s), Paragraph("Downloadable PDF", body_s), Paragraph("Compiles IEEE reliability indices (SAIFI/SAIDI), peak demands, and costs", body_s)],
        [Paragraph("Mobile Alerter", body_s), Paragraph("Telegram Bot API (httpx)", body_s), Paragraph("HTTPS Webhooks (Port 443)", body_s), Paragraph("Dispatches push alerts for source failure, 2-sigma trips, and stuck contactors", body_s)],
        [Paragraph("CLI Console UI", body_s), Paragraph("Terminal VT100 / ANSI", body_s), Paragraph("Standard Output (stdout)", body_s), Paragraph("ASCII capacity bar, system uptime, and remote tunnel link URLs", body_s)],
    ]
    t_front = Table(front_table_data, colWidths=[90, 120, 110, 184])
    t_front.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_front)
    story.append(Spacer(1, 8))

    # Section 2: Line-by-Line Dissection: grid_dashboard.py
    story.append(Paragraph("2. Detailed Line-by-Line Dissection: src/dashboard/grid_dashboard.py", h1_s))

    # Chunk 1
    story.append(add_chunk(
        "Section 2.1: FastAPI App Initialization & Global Shared State (Lines 1–65)",
        """39: app = FastAPI(title="Industrial Smart Grid SCADA & Digital Twin")
41: # Global Shared State Dictionary
42: latest_telemetry: Dict[str, Any] = {
43:     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
44:     "esp32_online": False,
45:     "hardware_status": "OFFLINE",
47:     "mode": "DUAL SMPS",
48:     "current_limit": 5000.0,
49:     "total_current": 0.0,
50:     "total_power": 0.0,
51:     "predicted_current": 0.0,
52:     "predicted_power": 0.0,
55:     "control_mode": "AUTO",
60:     "sources": {"smps1": False, "smps2": False, "battery": False},
61:     "critical": {"voltage": 12.0, "current": 300.0, "power": 3600.0},
62:     "hospital": {"voltage": 12.0, "current": 0.0, "power": 0.0, "relay": 1, "priority": 4},
63:     "street":   {"voltage": 12.0, "current": 0.0, "power": 0.0, "relay": 1, "priority": 3},
64:     "house":    {"voltage": 12.0, "current": 0.0, "power": 0.0, "relay": 1, "priority": 2},
65:     "industry": {"voltage": 12.0, "current": 0.0, "power": 0.0, "relay": 1, "priority": 1}
66: }""",
        [
            "<b>Lines 39–40:</b> Initializes the core FastAPI application instance with title and OpenAPI metadata.",
            "<b>Lines 42–66:</b> Defines the thread-safe global telemetry state dictionary. It mirrors the exact nested JSON schema emitted by the ESP32 hardware and updated by the backend MQTT loop at 1.0 Hz."
        ]
    ))

    # Chunk 2
    story.append(add_chunk(
        "Section 2.2: Thread-Safe WebSocket Connection Pooling (Lines 100–140)",
        """102: class ConnectionManager:
103:     def __init__(self):
104:         self.active_connections: List[WebSocket] = []
106:     async def connect(self, websocket: WebSocket):
107:         await websocket.accept()
108:         self.active_connections.append(websocket)
110:     def disconnect(self, websocket: WebSocket):
111:         if websocket in self.active_connections:
112:             self.active_connections.remove(websocket)
114:     async def broadcast(self, message: dict):
115:         for connection in list(self.active_connections):
116:             try:
117:                 await connection.send_json(message)
118:             except Exception:
119:                 self.disconnect(connection)
122: manager = ConnectionManager()""",
        [
            "<b>Lines 102–108:</b> Implements active WebSocket connection pooling. Accepts incoming client upgrade handshakes and registers browser client sockets.",
            "<b>Lines 114–119 (Resilient Broadcasting):</b> Broadcasts telemetry JSON packets to all connected operator screens. If a browser tab is abruptly closed or network drops, it gracefully purges the stale socket without throwing unhandled exceptions."
        ]
    ))

    # Chunk 3
    story.append(add_chunk(
        "Section 2.3: REST Actuation Control & Safety Dwell Interception (Lines 170–215)",
        """180: @app.post("/api/control/relay")
181: async def control_relay(request: Request):
182:     data = await request.json()
183:     load = data.get("load", "").lower()
184:     state = int(data.get("state", 1))
185:     # Enforce Dwell-Time Safety Lockout
186:     allowed, reason = safety_engine.validate_manual_switch(load, state)
187:     if not allowed:
188:         raise HTTPException(status_code=429, detail=reason)
189:     # Publish to MQTT Actuator Topic
190:     payload = {"cmd": "MANUAL", "load": load, "state": state, "reason": "Operator Override"}
191:     mqtt_client.publish(config.mqtt_topic_control, json.dumps(payload), qos=1)
192:     return {"status": "SUCCESS", "load": load, "state": state}
195: @app.post("/api/control/mode")
196: async def set_control_mode(request: Request):
197:     data = await request.json()
198:     mode = data.get("mode", "AUTO").upper()
199:     safety_engine.control_mode = mode
200:     return {"status": "SUCCESS", "control_mode": mode}""",
        [
            "<b>Lines 180–188:</b> Human operator relay actuation endpoint. <b>Crucial Safety Guard:</b> Human commands are validated against <code>safety_engine.validate_manual_switch()</code>. If an operator tries to toggle a relay before the 15s dwell time expires, it rejects the request with HTTP 429.",
            "<b>Lines 189–192:</b> Transmits the validated actuation payload to HiveMQ over MQTT QoS 1.",
            "<b>Lines 195–200:</b> Allows the operator to toggle between <code>AUTO</code> (Safety Governor controls relays) and <code>MANUAL</code> mode."
        ]
    ))

    # Chunk 4
    story.append(add_chunk(
        "Section 2.4: 1 Hz Cyclic WebSocket Push Loop & Client Endpoint (Lines 220–250)",
        """220: async def telemetry_broadcaster():
221:     while True:
222:         if manager.active_connections:
223:             await manager.broadcast(latest_telemetry)
224:         await asyncio.sleep(config.update_interval_sec)  # 1.0s interval
227: @app.websocket("/ws/telemetry")
228: async def websocket_endpoint(websocket: WebSocket):
229:     await manager.connect(websocket)
230:     try:
231:         while True:
232:             _ = await websocket.receive_text()  # Keep-alive heartbeat
233:     except WebSocketDisconnect:
234:         manager.disconnect(websocket)""",
        [
            "<b>Lines 220–224:</b> Background async worker looping continuously, broadcasting the latest telemetry state every second.",
            "<b>Lines 227–234:</b> WebSocket endpoint maintaining persistent full-duplex communication with connected browser clients."
        ]
    ))

    # Section 3: grid_analytics.py
    story.append(Paragraph("3. Detailed Dissection: src/services/grid_analytics.py", h1_s))
    story.append(add_chunk(
        "Section 3.1: Energy Integration, IEEE Reliability & Financial Billing",
        """61: def compute_analytics(df_tel: pd.DataFrame, df_act: pd.DataFrame, tariff: float = DEFAULT_TARIFF_PER_KWH) -> dict:
75:     # 1. Numerical kWh Integration via Trapezoidal Riemann Rule
76:     dt_hours = 2.0 / 3600.0  # 2-second sampling interval in hours
77:     kwh_hospital = (df_tel["hospital_power"].sum() / 1000.0) * dt_hours
78:     kwh_total    = (df_tel["total_power"].sum() / 1000.0) * dt_hours
82:     # 2. Financial Billing Integration (INR ₹)
83:     total_cost_inr = kwh_total * tariff
90:     # 3. IEEE Standard Grid Reliability Indices
91:     # SAIFI = Total Customer Interruptions / Total Customers
92:     # SAIDI = Total Interruption Durations / Total Customers
93:     saifi = float(len(df_act)) / 4.0
94:     saidi_minutes = (float(len(df_act)) * 15.0) / 60.0""",
        [
            "<b>Lines 75–78 (Numerical Energy Integration):</b> Converts discrete power readings into cumulative energy consumption using the Riemann sum: $E = \\sum P_k \\cdot \\Delta t$, dividing by 1000 to output kilowatt-hours (kWh).",
            "<b>Lines 82–83:</b> Computes commercial power bills using standard industrial tariff rates (₹8.00 / kWh).",
            "<b>Lines 90–94:</b> Formulates standard IEEE power distribution reliability indices: SAIFI (frequency of interruptions) and SAIDI (duration of outages)."
        ]
    ))

    story.append(add_chunk(
        "Section 3.2: Matplotlib Visual Chart Generation Engine",
        """120: def generate_analytics_charts(df_tel: pd.DataFrame, results_dir: str):
125:     # 1. Sector Energy Consumption Pie Chart
126:     fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
127:     sectors = ["Hospital", "Street", "House", "Industry", "Critical"]
128:     powers = [df_tel[f"{s.lower()}_power"].sum() for s in sectors]
129:     ax.pie(powers, labels=sectors, autopct='%1.1f%%', colors=['#2563eb', '#f59e0b', '#10b981', '#8b5cf6', '#dc2626'])
130:     fig.savefig(os.path.join(results_dir, "chart_energy_pie.png"), bbox_inches='tight')
140:     # 2. Voltage Stability Curve
141:     fig, ax = plt.subplots(figsize=(8, 4), dpi=300)
142:     ax.plot(df_tel["timestamp"], df_tel["critical_voltage"], color='#2563eb', label='Bus Voltage (V)')
143:     ax.axhline(12.0, color='gray', linestyle=':')
144:     fig.savefig(os.path.join(results_dir, "chart_voltage_stability.png"), bbox_inches='tight')""",
        [
            "<b>Lines 125–130:</b> Generates high-resolution 300 DPI sector energy consumption distribution charts.",
            "<b>Lines 140–144:</b> Visualizes bus voltage tracking against nominal $12.0\\text{ V}$ boundaries across source transitions."
        ]
    ))

    # Section 4: telegram_service.py
    story.append(Paragraph("4. Detailed Dissection: src/services/telegram_service.py", h1_s))
    story.append(add_chunk(
        "Section 4.1: Asynchronous Message Queue & Mobile Push Alerter",
        """28:         self._queue = queue.Queue(maxsize=250)
29:         self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
30:         self._worker_thread.start()
32:     def _worker_loop(self):
33:         while True:
34:             html_msg = self._queue.get()
36:             self._post_telegram_sync(html_msg)
37:             self._queue.task_done()
38:             time.sleep(0.3)  # Telegram API rate limit throttle
66:     def alert_actuation_event(self, action: str, load: str, reason: str, curr: float, limit: float):
75:         msg = f"⚡ <b>SMART GRID ACTION: {action}</b>\\n" \\
76:               f"Feeder: <b>{load.upper()}</b>\\n" \\
77:               f"Trigger Reason: <code>{reason}</code>\\n" \\
78:               f"Load at Event: <b>{curr:.1f} mA</b> / Limit: <b>{limit:.0f} mA</b>"
79:         self.dispatch_async(msg)""",
        [
            "<b>Lines 28–38:</b> Decouples notification dispatch onto a dedicated thread with a 250-item FIFO queue, ensuring external network latency never blocks the 1 Hz telemetry control loop.",
            "<b>Lines 66–79:</b> Formats structured mobile alert notifications and dispatches them asynchronously to the operator's phone."
        ]
    ))

    # Section 5: CLI Dashboard
    story.append(Paragraph("5. Detailed Dissection: src/smart_grid_ai.py (Terminal SCADA)", h1_s))
    story.append(add_chunk(
        "Section 5.1: Low-Overhead Terminal ASCII Dashboard (print_ascii_dashboard)",
        """97: def print_ascii_dashboard(row: dict, in_startup: bool, startup_rem: float, action_taken: str):
98:     limit = float(row.get("current_limit", 5000.0))
99:     tot_curr = float(row.get("total_current", 0.0))
100:     utilization = (tot_curr / limit * 100.0) if limit > 0 else 0.0
127:     # Dynamic Capacity Meter Bar
128:     bar_len = 35
129:     filled = int(min(utilization, 100.0) / 100.0 * bar_len)
130:     bar = "█" * filled + "░" * (bar_len - filled)
131:     print(f" CAPACITY   : [{bar}] {utilization:5.1f}%")
132:     print(f" TOTAL LOAD : {tot_curr:6.1f} mA / {limit:.0f} mA | PRED: {row.get('predicted_current', 0.0):6.1f} mA")""",
        [
            "<b>Lines 97–100:</b> Calculates real-time source capacity utilization percentage.",
            "<b>Lines 127–132:</b> Renders an ASCII status bar directly onto the server console, providing headless status monitoring without requiring a graphical display."
        ]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Done Part 2A PDF: {output_path}")

if __name__ == "__main__":
    out_pdf = r"C:\Users\lenovo\OneDrive\Documents\SMART_GRID_PROJECT\DEVELOPMENT\SMART_GRID_V2_UI_REDESIGN\docs\ESP32_SmartGrid_Part2A_Frontend_SCADA_Dashboard.pdf"
    build_part2a_pdf(out_pdf)
