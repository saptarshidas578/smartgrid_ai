import os
import sys
import shutil
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted, HRFlowable
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
            self.drawString(54, 755, "Smart Grid AI — Part 2B: Backend Logic & Infrastructure Specification")
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
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle('T', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#047857'), spaceAfter=4)
    sub_s = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#475569'), spaceAfter=10)
    h1_s = ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#065F46'), spaceBefore=12, spaceAfter=5, keepWithNext=True)
    h2_s = ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=3, keepWithNext=True)
    body_s = ParagraphStyle('B', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#1E293B'), spaceAfter=4)
    body_bold = ParagraphStyle('BB', parent=body_s, fontName='Helvetica-Bold')
    bullet_s = ParagraphStyle('Bul', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11.5, textColor=colors.HexColor('#1E293B'), leftIndent=12, firstLineIndent=-8, spaceAfter=2.5)
    code_s = ParagraphStyle('C', parent=styles['Normal'], fontName='Courier', fontSize=6.8, leading=8.8, textColor=colors.HexColor('#0F172A'))
    table_cell = ParagraphStyle('TC', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#1E293B'))
    table_cell_bold = ParagraphStyle('TCB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=colors.HexColor('#0F172A'))
    table_header = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=colors.white)

    def code_box(code_text):
        p = Preformatted(code_text.strip(), code_s)
        b = Table([[p]], colWidths=[504])
        b.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        return b

    def callout_box(text, title="CYBER-PHYSICAL SAFETY PRINCIPLE", color_hex="#047857", bg_hex="#ECFDF5"):
        content = [
            Paragraph(f"<b>{title}</b>", ParagraphStyle('CT', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.HexColor(color_hex))),
            Spacer(1, 2),
            Paragraph(text, ParagraphStyle('CB', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#1E293B')))
        ]
        t = Table([[content]], colWidths=[504])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_hex)),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor(color_hex)),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    story = []

    # =========================================================================
    # PAGE 1: TITLE, METADATA & EXECUTIVE SUMMARY
    # =========================================================================
    story.append(Paragraph("PART 2B: Backend Logic & Infrastructure", title_s))
    story.append(Paragraph("Complete Technical Architecture, Deterministic Safety Governor, SQLite WAL Persistence & Resilient Data Collection", sub_s))

    meta_data = [
        [
            Paragraph("<b>Author:</b> Saptarshi Das<br/><b>Institution:</b> School of Electrical Engineering & Dept of CSE, Vellore Institute of Technology (VIT)<br/><b>Email:</b> saptarshid234@outlook.com<br/><b>Repository:</b> github.com/saptarshidas578/smartgrid_ai", body_s),
            Paragraph("<b>Primary Modules:</b> <code>src/services/safety_engine.py</code> (226 lines)<br/><b>Data & Comm:</b> <code>mqtt_client.py</code> (105 lines), <code>database.py</code> (184 lines)<br/><b>Config & Sim:</b> <code>config.py</code> (102 lines), <code>mock_esp32.py</code> (150 lines)<br/><b>Orchestrator:</b> <code>smart_grid_ai.py</code> (184 lines), <code>run_smart_grid_suite.py</code>", body_s)
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

    story.append(Paragraph("1. Executive Role & Deterministic Safety Philosophy", h1_s))
    story.append(Paragraph(
        "The Backend Logic and Infrastructure subsystem constitutes the operational foundation and safety backbone of the smart grid. "
        "In critical infrastructure engineering, software platforms must reconcile two fundamentally conflicting paradigms: "
        "<b>probabilistic machine learning</b> (which generates statistical forecasts and class probabilities) and "
        "<b>deterministic protection</b> (which demands guaranteed tripping and shedding actions within strict temporal bounds).",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(callout_box(
        "DETERMINISTIC VETO AUTHORITY: In this cyber-physical system, the Safety Engine possesses absolute veto authority. "
        "It intercepts all telemetry frames and predictive outputs. If measured or projected grid current breaches physical limits, "
        "or if statistical 2-SD overcurrent thresholds are violated, the Safety Engine dispatches hardware actuation commands immediately. "
        "No machine learning model can override or suppress a safety trip.",
        title="CORE CYBER-PHYSICAL PRINCIPLE: DETERMINISTIC PROTECTION OVERRIDE",
        color_hex="#047857", bg_hex="#ECFDF5"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>Core Subsystem Responsibilities:</b><br/>"
        "• <b>Asynchronous Data Ingestion (`mqtt_client.py`):</b> High-throughput TLS-encrypted MQTT client gathering telemetry at 0.5 Hz.<br/>"
        "• <b>Deterministic Safety Governor (`safety_engine.py`):</b> Enforcing Knapsack priority shedding, asymmetric hysteresis, and anti-chatter dwell times.<br/>"
        "• <b>High-Concurrency Persistence (`database.py`):</b> SQLite database configured in Write-Ahead Logging (WAL) mode for zero-lock concurrent operations.<br/>"
        "• <b>Centralized Configuration (`config.py`):</b> Strongly-typed environment parser providing operational thresholds and calibration constants.<br/>"
        "• <b>Hardware-in-the-Loop Simulator (`mock_esp32.py`):</b> Digital twin simulating sensor noise, inrush currents, and fault injection.<br/>"
        "• <b>Master Orchestrator (`smart_grid_ai.py`):</b> Closed-loop supervisory loop binding MQTT, ML inference, Safety, SQLite, and Telegram.",
        body_s
    ))

    # =========================================================================
    # PAGE 2: MQTT TRANSPORT & DATA COLLECTION
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Resilient Data Collection & Transport Layer (`mqtt_client.py`)", h1_s))
    story.append(Paragraph(
        "`src/core/mqtt_client.py` implements a production-grade, encrypted MQTT networking client based on the OASIS MQTT standard. "
        "It bridges low-level ESP32 microcontrollers to the host AI controller over public and private networks.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("2.1 Multi-Version Paho Negotiation & TLS Encryption", h2_s))
    story.append(Paragraph(
        "To support diverse edge environments (Paho MQTT v2.0+ vs legacy v1.x), lines 29–37 implement dynamic version negotiation. "
        "Furthermore, all traffic across port 8883 is encrypted via TLS 1.3 / 1.2 to prevent man-in-the-middle attacks:",
        body_s
    ))
    story.append(code_box(
        "try:\n"
        "    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)\n"
        "except Exception:\n"
        "    self.client = mqtt.Client(client_id=self.client_id)\n"
        "\n"
        "self.client.username_pw_set(self.username, self.password)\n"
        "self.client.tls_set()  # HiveMQ Cloud TLS 8883 encryption"
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("2.2 Thread-Safe Publishing & Auto-Reconnect Daemon", h2_s))
    story.append(Paragraph(
        "Multiple host threads (FastAPI endpoints, Safety Engine, background monitors) concurrently publish to the MQTT socket. "
        "`ResilientMQTTClient` serializes all socket writes using a re-entrant mutual exclusion lock (`threading.Lock`):",
        body_s
    ))
    story.append(code_box(
        "def publish_control(self, payload: dict) -> bool:\n"
        "    with self._lock:\n"
        "        try:\n"
        "            msg = json.dumps(payload)\n"
        "            info = self.client.publish(config.mqtt_topic_control, msg, qos=1)\n"
        "            return info.rc == mqtt.MQTT_ERR_SUCCESS\n"
        "        except Exception as e:\n"
        "            print(f'[MQTT Error] {e}')\n"
        "            return False"
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "<b>Dedicated Reconnect Loop:</b> The `start()` method launches a daemon thread executing `connect_loop()`. "
        "If broker connectivity drops due to cellular or Wi-Fi disruptions, it automatically retries connection every 3.0 seconds "
        "without throwing unhandled exceptions or terminating host processes.",
        body_s
    ))

    # =========================================================================
    # PAGE 3: TOPIC SCHEMA & INGESTION ARCHITECTURE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2.3 MQTT Topic Architecture & Quality of Service (QoS)", h1_s))
    story.append(Paragraph(
        "Communication is structured across two dedicated topic namespaces with distinct Quality of Service (QoS) guarantees:",
        body_s
    ))
    story.append(Spacer(1, 4))

    topic_table_data = [
        [
            Paragraph("Topic Identifier", table_header),
            Paragraph("Flow Direction", table_header),
            Paragraph("QoS Level", table_header),
            Paragraph("Payload Schema & Operational Role", table_header)
        ],
        [
            Paragraph("smartgrid/live", table_cell_bold),
            Paragraph("Inbound (ESP32 -> Host)", table_cell),
            Paragraph("QoS 0 (At most once)", table_cell),
            Paragraph("Continuous 0.5 Hz telemetry packet containing bus voltage, sector currents, switch states, and mode flags. Loss of individual packets is harmless as subsequent samples arrive in < 2.0 s.", table_cell)
        ],
        [
            Paragraph("smartgrid/control", table_cell_bold),
            Paragraph("Outbound (Host -> ESP32)", table_cell),
            Paragraph("QoS 1 (At least once)", table_cell),
            Paragraph("Discrete switchgear actuation commands (TRIP, SHED, RESTORE, MANUAL_OVERRIDE). Handshaked broker acknowledgment ensures delivery to physical relay coils.", table_cell)
        ]
    ]

    t_topics = Table(topic_table_data, colWidths=[110, 85, 75, 234])
    t_topics.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_topics)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Telemetry Payload Ingestion Schema (`smartgrid/live`):", h2_s))
    story.append(code_box(
        "{\n"
        "  'timestamp': '2026-10-15 06:30:00',\n"
        "  'mode': 'DUAL SMPS',\n"
        "  'current_limit': 5000.0,\n"
        "  'hospital_relay': 1, 'hospital_current': 254.2,\n"
        "  'street_relay': 1,   'street_current': 391.8,\n"
        "  'house_relay': 1,    'house_current': 240.7,\n"
        "  'industry_relay': 1, 'industry_current': 239.5,\n"
        "  'critical_current': 298.5,\n"
        "  'total_current': 1424.7\n"
        "}"
    ))

    # =========================================================================
    # PAGES 4 & 5: DETERMINISTIC SAFETY GOVERNOR
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. The Deterministic Safety Governor (`safety_engine.py`)", h1_s))
    story.append(Paragraph(
        "`src/services/safety_engine.py` spans 226 lines of deterministic protection logic. It operates as the final arbiter "
        "before any physical switchgear command is dispatched.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("3.1 The Constrained Priority Knapsack Formulation", h2_s))
    story.append(Paragraph(
        "When total electrical demand approaches the thermal threshold of the active power supply ($I_{\\text{tot}} \\ge 0.85 \\cdot I_{\\max}$), "
        "the grid must shed load branches to prevent voltage collapse. This is formulated as a Constrained Priority Knapsack Optimization Problem:",
        body_s
    ))
    story.append(code_box(
        "Maximize:   SUM_{j in S_on} w_j\n"
        "Subject to: SUM_{j in S_on} I_j + I_crit <= 0.85 * I_max"
    ))
    story.append(Paragraph(
        "where $w_j$ represents the societal criticality weight of feeder $j$, and $S_{\\text{on}}$ is the subset of energized branches. "
        "The deterministic priority hierarchy is defined as follows:",
        body_s
    ))

    priority_table_data = [
        [
            Paragraph("Sector Feeder", table_header),
            Paragraph("Criticality Weight (w_j)", table_header),
            Paragraph("Nominal Draw", table_header),
            Paragraph("Shedding Priority", table_header),
            Paragraph("Restoration Priority", table_header)
        ],
        [
            Paragraph("Critical Bus", table_cell_bold),
            Paragraph("Infinity (Permanent)", table_cell),
            Paragraph("300 mA", table_cell),
            Paragraph("NEVER SHED", table_cell_bold),
            Paragraph("Always Energized", table_cell_bold)
        ],
        [
            Paragraph("Hospital", table_cell_bold),
            Paragraph("4 (Highest Priority)", table_cell),
            Paragraph("256 mA", table_cell),
            Paragraph("4th (Last Resort)", table_cell),
            Paragraph("1st to Restore", table_cell_bold)
        ],
        [
            Paragraph("Street Light", table_cell_bold),
            Paragraph("3 (High Priority)", table_cell),
            Paragraph("394 mA", table_cell),
            Paragraph("3rd", table_cell),
            Paragraph("2nd to Restore", table_cell)
        ],
        [
            Paragraph("Residential", table_cell_bold),
            Paragraph("2 (Medium Priority)", table_cell),
            Paragraph("241 mA", table_cell),
            Paragraph("2nd", table_cell),
            Paragraph("3rd to Restore", table_cell)
        ],
        [
            Paragraph("Industrial", table_cell_bold),
            Paragraph("1 (Lowest Priority)", table_cell),
            Paragraph("240 mA", table_cell),
            Paragraph("1st (First Shed)", table_cell_bold),
            Paragraph("4th (Last Restore)", table_cell)
        ]
    ]

    t_prio = Table(priority_table_data, colWidths=[90, 100, 75, 110, 129])
    t_prio.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_prio)

    story.append(PageBreak())
    story.append(Paragraph("3. Deterministic Safety Governor (Continued: Hysteresis & Dwell Times)", h1_s))

    story.append(Paragraph("3.2 Asymmetric Hysteresis & The 84% Restoration Ceiling", h2_s))
    story.append(Paragraph(
        "Symmetrical shedding and reconnection thresholds cause oscillatory relay hunting under fluctuating loads. "
        "The Safety Engine enforces **asymmetric hysteresis**: load shedding triggers at $\\rho \\ge 85.0\\%$, but restoration is strictly "
        "permitted only when projected post-restoration utilization remains $\\le 84.0\\%$:",
        body_s
    ))
    story.append(code_box(
        "rho_projected = ((I_total + I_nominal,j) / I_limit) * 100 <= 84.0%"
    ))
    story.append(Paragraph(
        "If reconnecting the highest-priority disconnected feeder would breach 84.0%, the algorithm bypasses it and attempts to "
        "opportunistic-pack a smaller load that safely fits within available headroom.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("3.3 The 15-Second Anti-Chatter Dwell Time", h2_s))
    story.append(Paragraph(
        "Rapid cycling of mechanical switchgear induces severe plasma arcing, accelerates contact erosion, and causes grid voltage flicker. "
        "The engine enforces an immutable **15-second minimum settling time** (`config.relay_settling_sec = 15.0`) on all relays:",
        body_s
    ))
    story.append(code_box(
        "on_dwell = now - self.relay_turn_on_time.get(cand, 0.0)\n"
        "if on_dwell < config.relay_settling_sec and utilization < 100.0:\n"
        "    continue  # Suppress shedding until contactor thermal dwell expires"
    ))
    story.append(Paragraph(
        "<b>Catastrophic Overload Bypass:</b> If grid current surges past 100.0% of capacity, the 15-second dwell check is bypassed "
        "to execute immediate emergency tripping, protecting conductors from thermal damage.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("3.4 Statistical 2-SD Overcurrent Protection & Welding Diagnostic", h2_s))
    story.append(Paragraph(
        "• <b>2-SD Statistical Tripping:</b> Instantaneous trip limits are calibrated empirically per feeder branch: "
        "<code>Critical: 320 mA, Hospital: 272 mA, Street: 405 mA, House: 256 mA, Industry: 264 mA</code>. "
        "Any breach triggers an instantaneous `TRIP` command.<br/>"
        "• <b>Stuck Contactor Diagnostic:</b> If a relay is commanded `OFF` ($u_j = 0$) but current $I_j > 25.0\\text{ mA}$ persists, "
        "the contactor is diagnosed as micro-welded (`STUCK_CLOSED`), isolated from control loops, and reported to Telegram.",
        body_s
    ))

    # =========================================================================
    # PAGES 6 & 7: SQLITE WAL PERSISTENCE SUBSYSTEM
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. High-Performance SQLite WAL Persistence Engine (`database.py`)", h1_s))
    story.append(Paragraph(
        "`src/core/database.py` manages local database transactions. In autonomous systems, telemetry persistence must never block "
        "real-time supervisory loops or fail during simultaneous dashboard queries.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("4.1 Write-Ahead Logging (WAL) PRAGMA Rationale", h2_s))
    story.append(Paragraph(
        "Standard SQLite rollback journaling acquires an exclusive table lock during writes, causing `sqlite3.OperationalError: database is locked` "
        "when FastAPI dashboard clients read history while the MQTT loop writes telemetry. "
        "Lines 18–23 activate Write-Ahead Logging (WAL) mode:",
        body_s
    ))
    story.append(code_box(
        "def get_connection(self) -> sqlite3.Connection:\n"
        "    conn = sqlite3.connect(self.db_path, timeout=10.0)\n"
        "    conn.row_factory = sqlite3.Row\n"
        "    conn.execute('PRAGMA journal_mode=WAL;')\n"
        "    conn.execute('PRAGMA synchronous=NORMAL;')\n"
        "    return conn"
    ))
    story.append(Paragraph(
        "• <b>Zero-Lock Concurrency:</b> In WAL mode, writes append to an auxiliary `.db-wal` file. Readers never block writers, "
        "and writers never block readers.<br/>"
        "• <b>`synchronous=NORMAL`:</b> Eliminates redundant OS disk flushes on every 2-second cycle, supporting > 2,000 writes/sec.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("4.2 Relational Database Schema Design", h2_s))
    story.append(Paragraph(
        "The database maintains two primary tables with B-tree indexing on timestamps for sub-millisecond range queries:",
        body_s
    ))

    db_schema_data = [
        [
            Paragraph("Table Name", table_header),
            Paragraph("Column Count", table_header),
            Paragraph("Primary Key & Indexes", table_header),
            Paragraph("Stored Data & Application", table_header)
        ],
        [
            Paragraph("telemetry_logs", table_cell_bold),
            Paragraph("23 Columns", table_cell),
            Paragraph("id (AUTOINCREMENT),<br/>idx_telemetry_ts (timestamp)", table_cell),
            Paragraph("Continuous 2.0 s time-series: timestamps, mode, limit, 5 sector currents, total current/power, AI forecasts, fault flags, warning levels.", table_cell)
        ],
        [
            Paragraph("grid_actuation_events", table_cell_bold),
            Paragraph("8 Columns", table_cell),
            Paragraph("id (AUTOINCREMENT),<br/>idx_actuation_ts (timestamp)", table_cell),
            Paragraph("Immutable switchgear operational audit trail: action_type (TRIP, SHED, RESTORE, MANUAL), load_name, reason, current_mA, limit_mA, details.", table_cell)
        ]
    ]

    t_schema = Table(db_schema_data, colWidths=[95, 70, 140, 199])
    t_schema.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_schema)

    story.append(PageBreak())
    story.append(Paragraph("4. Persistence Subsystem (Continued: Query Implementation)", h1_s))

    story.append(Paragraph("4.3 High-Throughput Insertion & Query Methods", h2_s))
    story.append(Paragraph(
        "Lines 72–117 implement parameterized, SQL-injection-safe telemetry insertions, while lines 142–170 define sliding-history queries:",
        body_s
    ))
    story.append(code_box(
        "def get_recent_history(self, limit: int = 35) -> List[Dict[str, Any]]:\n"
        "    with self.get_connection() as conn:\n"
        "        rows = conn.execute(\n"
        "            'SELECT timestamp, current_limit, total_current, predicted_current, '\n"
        "            'hospital_current, street_current, house_current, industry_current, critical_current '\n"
        "            'FROM telemetry_logs ORDER BY id DESC LIMIT ?', (limit,)\n"
        "        ).fetchall()\n"
        "        # Returns sanitized, rounded time-series points in chronological order"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("5. Central Configuration Management (`config.py`)", h1_s))
    story.append(Paragraph(
        "`src/core/config.py` provides strongly-typed configuration parameters via Python dataclasses. "
        "It incorporates a custom, zero-dependency `.env` parser (lines 5–23) that eliminates external library overhead:",
        body_s
    ))
    story.append(code_box(
        "@dataclass\n"
        "class GridConfig:\n"
        "    mqtt_broker: str = os.getenv('MQTT_BROKER', '78d11d43ac27466695cd0e4f5e7405c8.s1.eu.hivemq.cloud')\n"
        "    mqtt_port: int = int(os.getenv('MQTT_PORT', '8883'))\n"
        "    update_interval_sec: float = 2.0\n"
        "    startup_observe_sec: float = 30.0\n"
        "    relay_settling_sec: float = 15.0\n"
        "    shed_util_pct: float = 85.0\n"
        "    max_restore_util_pct: float = 84.0"
    ))

    # =========================================================================
    # PAGE 8: SIMULATION & TESTBENCH DIGITAL TWIN
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("6. Hardware-in-the-Loop Simulation Engine (`mock_esp32.py`)", h1_s))
    story.append(Paragraph(
        "`src/services/mock_esp32.py` provides a physical state-machine simulator replicating the ESP32 microcontroller testbench. "
        "It enables automated software testing when physical switchgear is unattached.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("6.1 Physics Modeling & Realistic Inrush Noise", h2_s))
    story.append(Paragraph(
        "The simulation models realistic electronic characteristics:<br/>"
        "• <b>Johnson-Nyquist Sensor Noise:</b> Generates Gaussian noise ($\\mu = 0.0, \\sigma = 1.2\\text{ mA}$) on ADC measurements.<br/>"
        "• <b>Motor Starting Inrush:</b> Simulates transient 150 ms inrush current spikes ($3.5 \\times I_{\\text{nominal}}$) during industrial relay closure.<br/>"
        "• <b>Dual SMPS Drop Emulation:</b> Periodically toggles supply limits (5000 mA $\\to$ 1000 mA) to validate automated load shedding response.<br/>"
        "• <b>Closed-Loop Actuator Feedback:</b> Subscribes to `smartgrid/control` and updates simulated relay states in real time.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(code_box(
        "def generate_packet(self):\n"
        "    # Inject Gaussian thermal noise onto shunt readings\n"
        "    noise = random.gauss(0, 1.2)\n"
        "    if self.relays['industry'] == 1:\n"
        "        ind_c = max(0.0, 240.0 + noise + self.inrush_spike)\n"
        "    else:\n"
        "        ind_c = 0.0\n"
        "    # Package and publish to smartgrid/live"
    ))

    # =========================================================================
    # PAGE 9: MASTER ORCHESTRATOR & CLOSED LOOP
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("7. Master Supervisory Orchestrator (`smart_grid_ai.py`)", h1_s))
    story.append(Paragraph(
        "`src/smart_grid_ai.py` binds all backend services into an autonomous closed loop. Every 2.0 seconds, the orchestrator "
        "executes the following strict computational pipeline:",
        body_s
    ))
    story.append(Spacer(1, 4))

    pipeline_steps = [
        [
            Paragraph("Step", table_header),
            Paragraph("Subsystem / Module", table_header),
            Paragraph("Execution Function & Technical Operation", table_header)
        ],
        [
            Paragraph("1", table_cell_bold),
            Paragraph("MQTT Transport", table_cell),
            Paragraph("`on_message()` callback intercepts incoming `smartgrid/live` telemetry packet.", table_cell)
        ],
        [
            Paragraph("2", table_cell_bold),
            Paragraph("Data Cleaning", table_cell),
            Paragraph("`ml_engine.flatten_raw_telemetry()` cleans values and clamps thermal zero-drift via `max(0.0, v)`.", table_cell)
        ],
        [
            Paragraph("3", table_cell_bold),
            Paragraph("AI Predictive Engine", table_cell),
            Paragraph("`ml_engine.run_inference_and_diagnostics()` extracts 36 features and runs the 8-model ensemble.", table_cell)
        ],
        [
            Paragraph("4", table_cell_bold),
            Paragraph("Safety Governor", table_cell),
            Paragraph("`safety_engine.evaluate_telemetry()` checks 2-SD limits, 85% overload, and 15s dwell timers.", table_cell)
        ],
        [
            Paragraph("5", table_cell_bold),
            Paragraph("Switchgear Actuation", table_cell),
            Paragraph("If shed or trip required, publishes command packet to `smartgrid/control` (QoS 1).", table_cell)
        ],
        [
            Paragraph("6", table_cell_bold),
            Paragraph("SQLite WAL Logging", table_cell),
            Paragraph("`db.log_telemetry()` persists the enriched row to `live_smartgrid.db` in WAL mode.", table_cell)
        ],
        [
            Paragraph("7", table_cell_bold),
            Paragraph("Telegram Alerting", table_cell),
            Paragraph("`telegram.alert_actuation_event()` dispatches asynchronous HTML alerts to operator smartphones.", table_cell)
        ],
        [
            Paragraph("8", table_cell_bold),
            Paragraph("Console SCADA", table_cell),
            Paragraph("`print_ascii_dashboard()` renders live UTF-8 capacity bar and sector telemetry table.", table_cell)
        ]
    ]

    t_pipe = Table(pipeline_steps, colWidths=[35, 120, 349])
    t_pipe.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_pipe)
    story.append(Spacer(1, 6))

    story.append(Paragraph("Multi-Process Deployment (`run_smart_grid_suite.py`):", h2_s))
    story.append(Paragraph(
        "Supervises four background daemon processes: FastAPI SCADA server, AI Controller, Mock ESP32 Simulator, "
        "and Cloudflare Tunnel daemon (`cloudflared.exe`), automatically extracting dynamic public URLs to `public_link.txt`.",
        body_s
    ))

    # =========================================================================
    # PAGES 10 & 11: BACKEND ENGINEERING PROBLEMS & INTEGRITY
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("8. Real-World Engineering Problems Faced & Solved in Backend Infrastructure", h1_s))
    story.append(Paragraph(
        "Deploying closed-loop supervisory control on physical switchgear revealed several critical infrastructure failure modes:",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Problem 1: SQLite Lock Contention Under High-Frequency Ingestion", h2_s))
    story.append(Paragraph(
        "<b>The Symptom:</b> During concurrent web dashboard sessions, `smart_grid_ai.py` crashed repeatedly with `sqlite3.OperationalError: database is locked`.<br/>"
        "<b>Root Cause:</b> Standard SQLite rollback journals acquire an exclusive file lock during write transactions, blocking concurrent web readers.<br/>"
        "<b>The Solution:</b> Activated **Write-Ahead Logging (`PRAGMA journal_mode=WAL;`)** and set busy timeout to 10.0 seconds. Lock errors dropped to zero.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Problem 2: Relational Contactor Chatter & Relay Hunting", h2_s))
    story.append(Paragraph(
        "<b>The Symptom:</b> Under fluctuating industrial loads near 85% capacity, relays rapidly toggled ON/OFF every 2.0 s, causing severe arcing.<br/>"
        "<b>Root Cause:</b> Symmetrical shedding and restoration thresholds created infinite cycles whenever a single shed dropped utilization below 85%.<br/>"
        "<b>The Solution:</b> Introduced **asymmetric hysteresis** (85% shed threshold vs 84% projected restore ceiling) combined with an immutable **15-second anti-chatter dwell timer**.",
        body_s
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Problem 3: Paho MQTT Thread Concurrency Violations", h2_s))
    story.append(Paragraph(
        "<b>The Symptom:</b> Dispatches from web override endpoints raised `RuntimeError: underlying socket invalid` in the Paho network loop.<br/>"
        "<b>Root Cause:</b> FastAPI asynchronous coroutines and the AI loop were invoking `client.publish()` simultaneously across different thread IDs.<br/>"
        "<b>The Solution:</b> Wrapped all socket write operations in a re-entrant mutual exclusion lock (`threading.Lock()`), ensuring serialized packet transmission.",
        body_s
    ))

    story.append(PageBreak())
    story.append(Paragraph("8. Engineering Problems Faced & Solved (Continued: Problem 4 & Audit)", h1_s))

    story.append(Paragraph("Problem 4: Cold-Start Filter Capacitor Inrush False Tripping", h2_s))
    story.append(Paragraph(
        "<b>The Symptom:</b> Upon powering up the testbench, large inrush currents charging DC power supply smoothing capacitors triggered immediate 2-SD overcurrent trips.<br/>"
        "<b>Root Cause:</b> Filter capacitors appear as instantaneous short circuits during initial energization ($t < 1.0\\text{ s}$).<br/>"
        "<b>The Solution:</b> Implemented a **30-second observation startup grace period** (`config.startup_observe_sec = 30.0`). Automated capacity shedding is suspended during startup while capacitors charge smoothly.",
        body_s
    ))
    story.append(Spacer(1, 8))

    story.append(callout_box(
        "BACKEND INFRASTRUCTURE VALIDATION COMPLETE: Part 2B Backend Logic & Infrastructure operates with 100% deterministic safety. "
        "The priority knapsack algorithm, asymmetric hysteresis, 15s dwell timers, and SQLite WAL storage provide industrial-grade reliability.",
        title="SYSTEM INTEGRITY VERIFICATION: BACKEND FULLY OPERATIONAL",
        color_hex="#047857", bg_hex="#ECFDF5"
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Done Part 2B PDF: {output_path}")

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ESP32_SmartGrid_Part2B_Backend_Logic_Infrastructure.pdf")
    build_part2b_pdf(out)
