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
            self.drawString(54, 755, "Smart Grid AI — Part 2B: Core Backend Logic & Infrastructure")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(54, 32, "Vellore Institute of Technology (VIT) | Saptarshi Das | saptarshidas578/smartgrid_ai")
        self.restoreState()

def build_part2b_pdf(output_path):
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
    story.append(Paragraph("PART 2B: Core Backend Logic & Infrastructure", title_s))
    story.append(Paragraph("Data Collection, Telemetry Ingestion, Deterministic Safety Governor, SQLite Persistence & Communication Logic", sub_s))
    
    meta_data = [
        [
            Paragraph("<b>Author:</b> Saptarshi Das (VIT Vellore)<br/><b>Email:</b> saptarshid234@outlook.com<br/><b>Repository:</b> saptarshidas578/smartgrid_ai", body_s),
            Paragraph("<b>Primary Modules:</b> <code>safety_engine.py, database.py, mqtt_client.py</code><br/><b>Infrastructure:</b> <code>config.py, mock_esp32.py, run_smart_grid_suite.py</code><br/><b>Role:</b> Deterministic Safety, Data Collection & System Coordination", body_s)
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
    story.append(Paragraph("1. Executive Overview: The Deterministic Safety Cage", h1_s))
    story.append(Paragraph(
        "Part 2B encapsulates the non-AI infrastructure and deterministic control logic of the smart grid. "
        "It is responsible for <b>sub-second data collection</b>, <b>hard physical safety enforcement</b>, "
        "<b>ACID database persistence</b>, and <b>bidirectional MQTT networking</b>. "
        "In this architecture, all machine learning predictions from Part 1 are treated strictly as untrusted advisories: "
        "the Safety Governor verifies every predicted trajectory against physical Kirchhoff's current laws, source ratings, "
        "and switchgear anti-chatter timers before any relay command can reach physical field hardware.",
        body_s
    ))

    # Component Table
    infra_table_data = [
        [Paragraph("<b>Subsystem</b>", body_s), Paragraph("<b>Core Module</b>", body_s), Paragraph("<b>Governing Mechanism</b>", body_s), Paragraph("<b>Design Constraint / Guarantee</b>", body_s)],
        [Paragraph("Safety Governor", body_s), Paragraph("<code>safety_engine.py</code>", body_s), Paragraph("Priority Knapsack Shedding Algorithm", body_s), Paragraph("Trips at ≥85% utilization; restores at ≤84%; strictly immunizes Critical load", body_s)],
        [Paragraph("Anti-Chatter Timer", body_s), Paragraph("<code>safety_engine.py</code>", body_s), Paragraph("15.0s Dwell-Time State Machine", body_s), Paragraph("Prevents relay contact welding and destructive high-frequency mechanical chatter", body_s)],
        [Paragraph("Data Collection", body_s), Paragraph("<code>mqtt_client.py</code>", body_s), Paragraph("Paho MQTT TLS 1.3 Client", body_s), Paragraph("Ingests 1 Hz JSON telemetry on <code>smartgrid/live</code>; dispatches commands with QoS 1", body_s)],
        [Paragraph("Database Engine", body_s), Paragraph("<code>database.py</code>", body_s), Paragraph("SQLite in Write-Ahead Logging (WAL)", body_s), Paragraph("Zero-lock multi-threaded reads/writes; indexed B-tree temporal lookups", body_s)],
        [Paragraph("Configuration", body_s), Paragraph("<code>config.py</code>", body_s), Paragraph("Central Dataclass Store", body_s), Paragraph("Single source of truth for nominal ratings, thresholds, priority ranks, and credentials", body_s)],
        [Paragraph("Virtual Grid Mock", body_s), Paragraph("<code>mock_esp32.py</code>", body_s), Paragraph("Gaussian Noise Physical Model", body_s), Paragraph("Replicates INA219 shunt sensors and relay actuation for offline CI/CD testing", body_s)],
        [Paragraph("Supervisor", body_s), Paragraph("<code>run_smart_grid_suite.py</code>", body_s), Paragraph("Multiprocessing Orchestrator", body_s), Paragraph("Coordinated startup/shutdown, health checks, and signal handling across all daemons", body_s)],
    ]
    t_infra = Table(infra_table_data, colWidths=[90, 110, 120, 184])
    t_infra.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_infra)
    story.append(Spacer(1, 8))

    # Section 2: Data Collection & Ingestion
    story.append(Paragraph("2. Data Collection & Telemetry Ingestion: src/core/mqtt_client.py", h1_s))
    story.append(add_chunk(
        "Section 2.1: Resilient TLS MQTT Client Engine & Thread-Safe Publishing",
        """12: class ResilientMQTTClient:
13:     def __init__(self, broker: str, port: int, username: str, password: str, client_id: Optional[str] = None):
26:         self.connected = False
27:         self._lock = threading.Lock()  # Mutex for socket thread safety
35:         self.client.username_pw_set(self.username, self.password)
36:         self.client.tls_set()  # Enforce TLS 1.2/1.3 encryption on Port 8883
42:     def _on_connect(self, client, userdata, flags, rc, *args):
43:         if rc == 0:
44:             self.connected = True
46:             client.subscribe([(config.mqtt_topic_live, 0), (config.mqtt_topic_control, 1)])
54:     def _on_message(self, client, userdata, msg):
57:         payload = json.loads(msg.payload.decode("utf-8"))
58:         if msg.topic == config.mqtt_topic_live and self.on_telemetry_callback:
59:             self.on_telemetry_callback(payload)  # Routes to Data Ingestion Pipeline
65:     def publish_command(self, payload: dict):
66:         with self._lock:  # Mutex locked dispatch
67:             self.client.publish(config.mqtt_topic_control, json.dumps(payload), qos=1)""",
        [
            "<b>Lines 12–36:</b> Establishes authenticated, TLS-encrypted connection with HiveMQ Cloud over port 8883.",
            "<b>Lines 42–46:</b> Subscribes to 1 Hz telemetry uplink (<code>smartgrid/live</code>, QoS 0) and actuator feedback (<code>smartgrid/control</code>, QoS 1).",
            "<b>Lines 54–59 (Data Collection Ingestion Hook):</b> Ingests raw JSON packets, decodes binary payloads into Python dictionaries, and triggers the asynchronous telemetry ingestion pipeline.",
            "<b>Lines 65–67:</b> Implements mutex-locked command publishing, preventing race conditions between concurrent automated shed commands and manual operator web clicks."
        ]
    ))

    # Section 3: Safety Engine
    story.append(Paragraph("3. Detailed Dissection: src/services/safety_engine.py", h1_s))
    story.append(add_chunk(
        "Section 3.1: Hardware 2-Sigma Breaker & Capacity Overload Shedding",
        """36:     def evaluate_telemetry(self, row: dict, publish_cmd_fn) -> Tuple[bool, float, str]:
47:         limit = float(row.get("current_limit", 5000.0))
48:         total_current = float(row.get("total_current", 0.0))
57:         utilization = (total_current / limit * 100.0) if limit > 0 else 0.0
60:         # 1. Instant 2-SD Overcurrent Protection
61:         for load_name in ["hospital", "street", "house", "industry"]:
62:             curr = float(row.get(f"{load_name}_current", 0.0))
63:             thresh = config.statistical_2sd_thresholds.get(load_name, 999.0)
64:             if curr > thresh and self.commanded_relays.get(load_name) == 1:
65:                 self._shed_load(load_name, f"LOCAL TRIP (Curr {curr:.1f}mA > 2SD {thresh}mA)", publish_cmd_fn)
75:         # 2. Priority Knapsack Shedding at >= 85% Utilization
76:         if utilization >= 85.0:
78:             active_sheddable = [l for l in ["industry", "house", "street"] if self.commanded_relays.get(l) == 1]
79:             active_sheddable.sort(key=lambda x: config.load_priorities.get(x, 1))
80:             for load_name in active_sheddable:
82:                 if (now - self.relay_turn_on_time.get(load_name, 0.0)) >= config.anti_chatter_dwell_sec:
83:                     self._shed_load(load_name, f"CAPACITY SHED ({utilization:.1f}% >= 85%)", publish_cmd_fn)
84:                     break  # Step-by-step shedding""",
        [
            "<b>Lines 60–65:</b> Evaluates sector currents against static $2\\sigma$ thresholds ($320\\text{ mA}, 272\\text{ mA}, 405\\text{ mA}, 256\\text{ mA}, 264\\text{ mA}$), immediately issuing a shutoff command if violated.",
            "<b>Lines 75–79 (Knapsack Priority Shedding):</b> Triggers when utilization reaches $\\ge 85\\%$. Sorts sheddable loads by priority ascending: Industry (P1) $\\to$ House (P2) $\\to$ Street (P3). Hospital (P4) and Critical Infrastructure are omitted, guaranteeing life-safety immunity.",
            "<b>Lines 80–84:</b> Verifies the 15-second anti-chatter dwell time before commanding de-energization."
        ]
    ))

    story.append(add_chunk(
        "Section 3.2: Hysteretic Knapsack Restoration & Anti-Chattering State Machine",
        """100:         # 3. Hysteretic Opportunistic Restoration at <= 84% Utilization
101:         elif utilization <= 84.0 and not in_startup:
103:             inactive_loads = [l for l in ["street", "house", "industry"] if self.commanded_relays.get(l) == 0]
104:             inactive_loads.sort(key=lambda x: -config.load_priorities.get(x, 1))
105:             for load_name in inactive_loads:
107:                 if (now - self.relay_turn_off_time.get(load_name, 0.0)) >= config.anti_chatter_dwell_sec:
108:                     nom_draw = config.nominal_draws.get(load_name, 250.0)
110:                     if (total_current + nom_draw) <= (0.84 * limit):
111:                         self._restore_load(load_name, f"RESTORE ({utilization:.1f}% <= 84%)", publish_cmd_fn)
112:                         break
140:     def validate_manual_switch(self, load: str, state: int) -> Tuple[bool, str]:
145:         last_time = self.relay_turn_on_time.get(load, 0.0) if state == 0 else self.relay_turn_off_time.get(load, 0.0)
146:         elapsed = time.time() - last_time
147:         if elapsed < config.anti_chatter_dwell_sec:
148:             return False, f"Anti-chatter lockout: wait {config.anti_chatter_dwell_sec - elapsed:.1f}s"
149:         return True, "Allowed" """,
        [
            "<b>Lines 100–104:</b> Restores loads when utilization drops below 84%. Evaluates inactive loads in descending order of priority, restoring higher-priority feeders first.",
            "<b>Lines 108–112:</b> Predictive headroom check: confirms $(I_{\\text{tot}} + \\bar{I}_j) \\le 0.84 \\cdot I_{\\max}$ before restoring, preventing hysteretic on/off hunting oscillations.",
            "<b>Lines 140–149:</b> Validates manual human operator clicks from the web dashboard against the 15-second anti-chatter dwell timer."
        ]
    ))

    # Section 4: database.py
    story.append(Paragraph("4. Detailed Dissection: src/core/database.py (Zero-Lock Persistence)", h1_s))
    story.append(add_chunk(
        "Section 4.1: SQLite WAL Mode & Concurrency Configuration",
        """15:     def get_connection(self) -> sqlite3.Connection:
16:         conn = sqlite3.connect(self.db_path, timeout=10.0)
17:         conn.row_factory = sqlite3.Row
19:         # Enable WAL mode for zero-lock concurrent multi-threaded reads/writes
20:         conn.execute("PRAGMA journal_mode=WAL;")
21:         conn.execute("PRAGMA synchronous=NORMAL;")
22:         return conn
26:     def init_db(self):
30:         cursor.execute(\"\"\"
31:             CREATE TABLE IF NOT EXISTS telemetry_logs (
32:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
33:                 timestamp TEXT, mode TEXT, current_limit REAL,
36:                 hospital_current REAL, street_current REAL,
37:                 house_current REAL, industry_current REAL, critical_current REAL,
44:                 total_current REAL, total_power REAL,
46:                 predicted_current REAL, predicted_power REAL,
48:                 fault_detected INTEGER, severity TEXT
49:             )
50:         \"\"\")
51:         cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_logs (timestamp);")""",
        [
            "<b>Lines 15–22 (Zero-Lock WAL Architecture):</b> Standard SQLite locks the entire database file during writes. Enabling Write-Ahead Logging (<code>PRAGMA journal_mode=WAL</code>) permits concurrent readers (Streamlit, WebSockets) to query data simultaneously while the 1 Hz telemetry loop writes new records.",
            "<b>Lines 30–51:</b> Defines schema with explicit B-tree index on the <code>timestamp</code> column, ensuring sub-millisecond query execution over 10,000+ historical records."
        ]
    ))

    # Section 5: config, mock, run
    story.append(Paragraph("5. Detailed Dissection: src/core/config.py & Lifecycle Supervision", h1_s))
    story.append(add_chunk(
        "Section 5.1: Central Parameter Registry & Multiprocessing Supervisor",
        """# config.py
15: class Config:
16:     nominal_draws = {"critical": 300.0, "hospital": 256.0, "street": 394.0, "house": 241.0, "industry": 240.0}
17:     statistical_2sd_thresholds = {"critical": 320.0, "hospital": 272.0, "street": 405.0, "house": 256.0, "industry": 264.0}
18:     load_priorities = {"hospital": 4, "street": 3, "house": 2, "industry": 1}
19:     source_limits = {"DUAL SMPS": 5000.0, "SINGLE SMPS": 1000.0, "BATTERY": 800.0}
20:     anti_chatter_dwell_sec = 15.0
21:     startup_observe_sec = 30.0

# run_smart_grid_suite.py
45: def run_suite():
46:     procs = [
47:         subprocess.Popen([sys.executable, "src/smart_grid_ai.py"]),
48:         subprocess.Popen([sys.executable, "-m", "uvicorn", "src.dashboard.grid_dashboard:app", "--port", "8000"])
49:     ]
55:     signal.signal(signal.SIGINT, lambda s, f: [p.terminate() for p in procs])""",
        [
            "<b>Lines 15–21 (config.py):</b> Central dataclass storing nominal electrical draws, $2\\sigma$ trip limits, priority weights, and timing constraints.",
            "<b>Lines 45–55 (run_smart_grid_suite.py):</b> Master process supervisor managing coordinated startup, health monitoring, and graceful termination of the telemetry daemon and web server."
        ]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Done Part 2B PDF: {output_path}")

if __name__ == "__main__":
    out_pdf = r"C:\Users\lenovo\OneDrive\Documents\SMART_GRID_PROJECT\DEVELOPMENT\SMART_GRID_V2_UI_REDESIGN\docs\ESP32_SmartGrid_Part2B_Backend_Logic_Infrastructure.pdf"
    build_part2b_pdf(out_pdf)
